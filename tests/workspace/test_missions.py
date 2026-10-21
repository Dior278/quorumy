"""Research cancellation and failures must not leave live or successful ghosts."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from quorumy.workspace.core.models import SpeechPlan
from quorumy.workspace.core.tools import ToolSpec
from tests.workspace.test_engine import FakeDecision, MemoryStore, ResearchGenerator
from tests.workspace.test_quorumy import make_engine


async def research_engine(handler, generator=None):
    engine, events = make_engine(
        MemoryStore(),
        generator=generator or ResearchGenerator(),
        decision=FakeDecision("investigate", initiative="proactive"),
    )
    engine.coordinator.tools.register(
        ToolSpec(
            name="fake_search",
            description="Test search",
            input_schema={},
            effect="read",
            handler=handler,
        )
    )
    engine.speaker.report_task = AsyncMock(return_value=SpeechPlan())
    await engine.start()
    await engine.start_session({"capture_mode": "text", "consent": True})
    return engine, events


async def wait_until(predicate):
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_timeout_cancels_provider_and_next_mission_can_succeed():
    released = asyncio.Event()

    async def blocked(_):
        try:
            await asyncio.Event().wait()
        finally:
            released.set()

    tool = AsyncMock(side_effect=blocked)
    engine, _ = await research_engine(tool)
    engine.config.policy.mission_timeout_seconds = 0.05
    try:
        await engine.commit_utterance("Quorumy, recherche la source.", source="manual")
        await asyncio.wait_for(engine.drain(), 1)
        failed = engine.state.tasks[-1]
        assert released.is_set()
        assert failed.status == "failed" and failed.error == "mission_timeout"
        assert failed.completed_at and failed.duration_ms >= 0
        assert not any(run.status == "running" for run in engine.state.agent_runs)
        tool.side_effect = None
        tool.return_value = {"status": "ok", "summary": "Evidence", "results": []}
        engine.config.policy.mission_timeout_seconds = 5
        await engine.commit_utterance("Quorumy, réessaie.", source="manual")
        await asyncio.wait_for(engine.drain(), 1)
        assert engine.state.tasks[-1].status == "done"
        assert (
            engine.state.tasks[-1].source_utterance_id == engine.state.transcript[-1].id
        )
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_cancel_queued_mission_does_not_cancel_other_research():
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked(_):
        entered.set()
        await release.wait()
        return {"status": "ok", "summary": "First result"}

    tool = AsyncMock(side_effect=blocked)
    engine, _ = await research_engine(tool)
    try:
        await engine.commit_utterance("Première recherche", source="manual")
        await asyncio.wait_for(entered.wait(), 1)
        first = engine.state.tasks[0]
        await engine.commit_utterance("Autre recherche", source="manual")
        await wait_until(lambda: len(engine.state.tasks) == 2)
        second = engine.state.tasks[-1]
        assert await engine.cancel_mission(second.id)
        assert first.status == "running"
        assert second.status == "canceled" and second.error == "canceled_by_user"
        release.set()
        await asyncio.wait_for(engine.drain(), 1)
        assert first.status == "done"
        assert tool.await_count == 1
        assert not await engine.cancel_mission(second.id)
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_cancel_running_mission_releases_provider_and_pending_voice():
    entered, released = asyncio.Event(), asyncio.Event()

    async def blocked(_):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            released.set()

    engine, events = await research_engine(blocked)
    engine.state.floor_busy = True
    try:
        await engine.commit_utterance("Recherche à annuler", source="manual")
        await asyncio.wait_for(entered.wait(), 1)
        task = engine.state.tasks[-1]
        await engine._offer_speaker_text(
            "Je prépare cette recherche.", "direct_address", [task.id]
        )
        await wait_until(lambda: bool(engine._delivery_audio))
        assert await engine.cancel_mission(task.id)
        await asyncio.wait_for(engine.drain(), 1)
        assert released.is_set()
        assert task.status == "canceled"
        assert not engine._delivery_audio and not engine._delivery_jobs
        assert not any(e["type"] == "speech.authorized" for e in events)
        assert not any(run.status == "running" for run in engine.state.agent_runs)
    finally:
        await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["exception", "unsuccessful_result", "planning"])
async def test_failed_research_never_becomes_successful(failure):
    async def tool(_):
        if failure == "exception":
            raise RuntimeError("private provider detail must not escape")
        return {"status": "unavailable", "error": "No evidence"}

    class BrokenPlanner(ResearchGenerator):
        async def generate(self, messages, model_id=None):
            if (
                failure == "planning"
                and "background missions" in messages[0]["content"]
            ):
                raise RuntimeError("private planner detail")
            return await super().generate(messages, model_id)

    engine, _ = await research_engine(tool, BrokenPlanner())
    try:
        await engine.commit_utterance("Quorumy, vérifie.", source="manual")
        await asyncio.wait_for(engine.drain(), 1)
        task = engine.state.tasks[-1]
        assert task.status == "failed" and task.phase == "complete"
        assert task.completed_at and task.duration_ms is not None
        assert "private" not in (task.error or "")
        assert not any(run.status == "running" for run in engine.state.agent_runs)
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_reused_result_keeps_evidence_and_does_not_call_provider_twice():
    tool = AsyncMock(
        return_value={
            "status": "ok",
            "summary": "Result",
            "results": [{"url": "https://example.org/evidence"}],
        }
    )
    engine, _ = await research_engine(tool)
    try:
        for _ in range(2):
            await engine.commit_utterance("Quorumy, même recherche.", source="manual")
            await asyncio.wait_for(engine.drain(), 1)
        first, second = engine.state.tasks
        assert first.status == second.status == "done"
        assert second.reused_from == first.id
        assert second.result == first.result and second.result is not first.result
        assert tool.await_count == 1
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_repeated_tool_selection_is_bounded_without_repeating_provider_calls():
    class LoopingPlanner(ResearchGenerator):
        async def generate(self, messages, model_id=None):
            if "background missions" in messages[0]["content"]:
                # Keep selecting exactly the same tool, even after its result.
                return await super().generate(messages[:2], model_id)
            return await super().generate(messages, model_id)

    tool = AsyncMock(return_value={"status": "ok", "summary": "Evidence"})
    engine, _ = await research_engine(tool, LoopingPlanner())
    try:
        await engine.commit_utterance("Quorumy, vérifie une source.", source="manual")
        await asyncio.wait_for(engine.drain(), 1)
        assert tool.await_count == 1
        assert engine.state.tasks[-1].status == "failed"
        assert engine.state.tasks[-1].error == "tool_step_limit"
        assert not any(card.title == "Tool loop stopped" for card in engine.state.cards)
    finally:
        await engine.stop()


def test_queued_research_keeps_its_request_when_the_conversation_moves_on():
    from quorumy.workspace.core.models import Decision, QuorumyState, Task, Utterance

    original = Utterance(text="Vérifie la documentation de WebRTC.")
    later = Utterance(text="Et cherche aussi la météo de demain.")
    state = QuorumyState(
        project_id="quorumy", protocol_version=12, transcript=[original, later]
    )
    engine, _ = make_engine(MemoryStore())
    task = Task(
        tool="pending_selection", summary=original.text, source_utterance_id=original.id
    )
    messages = engine.coordinator._messages(state, Decision(route="investigate"), task)
    context = json.loads(messages[-1]["content"])
    assert context["mission_request"]["text"] == original.text
    assert context["mission_request"]["utterance_id"] == original.id
    assert context["recent_transcript"][-1]["text"] == later.text
