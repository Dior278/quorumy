"""Regression coverage for Quorumy's meeting features."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from quorumy.minutes import Evidence, ProposedMinutes, ProposedNote, Review
from quorumy.workspace.adapters.sqlite import SQLiteStore
from quorumy.workspace.config import AppConfig, default_config_text, load_product
from quorumy.workspace.core.coordinator import Coordinator
from quorumy.workspace.core.models import (
    QuorumyState,
    SessionStatus,
    Utterance,
    now_iso,
)
from quorumy.workspace.core.speaker import SpeakerAgent
from quorumy.workspace.core.tools import ToolRegistry
from quorumy.workspace.runtime import WorkspaceEngine
from tests.workspace.test_engine import (
    FakeDecision,
    FakeGenerator,
    FakeTTS,
    TrackingSTT,
)


class MinutesBackend:
    def __init__(self):
        self.research_memory = {}
        self.calls = 0

    async def meeting_minutes(self, evidence):
        self.calls += 1
        u = evidence[0]
        return ProposedMinutes(
            notes=[
                ProposedNote(
                    kind="action",
                    text="Préparer le prototype.",
                    owner_id="renard",
                    due_quote=None,
                    evidence=[
                        Evidence(utterance_id=u["utterance_id"], quote=u["text"])
                    ],
                )
            ]
        )

    async def close(self):
        pass


def make_engine(store, generator=None, decision=None):
    generator = generator or FakeGenerator()
    config = AppConfig.model_validate_json(default_config_text())
    config.session.notes_interval_seconds = 3600
    published = []

    async def publish(message):
        published.append(message)

    engine = WorkspaceEngine(
        product=load_product(),
        config=config,
        store=store,
        decision=decision or FakeDecision("capture"),
        speaker=SpeakerAgent(generator),
        coordinator=Coordinator(
            generator, ToolRegistry(1), config.policy, config.llm.roles
        ),
        stt=TrackingSTT(),
        tts=FakeTTS(),
        publish=publish,
        tool_health={},
        backend=MinutesBackend(),
    )
    return engine, published


@pytest.mark.asyncio
async def test_text_consent_and_audio_permissions(tmp_path):
    engine, _ = make_engine(SQLiteStore(tmp_path / "test.sqlite3"))
    await engine.start()
    try:
        with pytest.raises(ValueError):
            await engine.start_session({"capture_mode": "text", "consent": False})
        await engine.start_session({"capture_mode": "text", "consent": True})
        await engine.ingest_audio(b"audio")
        assert engine.stt.starts == 0 and engine.state.pipeline.audio_bytes == 0
        await engine.session_command("pause")
        with pytest.raises(ValueError):
            await engine.session_command("resume")
        engine.state.consent_at = now_iso()
        await engine.session_command("resume")
        assert engine.state.session_status == SessionStatus.LISTENING
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_pause_cancels_work_without_new_extraction(tmp_path):
    engine, _ = make_engine(SQLiteStore(tmp_path / "test.sqlite3"))
    await engine.start()
    try:
        await engine.start_session({"capture_mode": "text", "consent": True})
        engine.coordinator.write_notes = AsyncMock()
        engine.state.transcript.append(Utterance(text="Information privée"))
        engine._notes_dirty = True
        work = engine._spawn(asyncio.sleep(60))
        await engine.session_command("pause")
        await engine.on_partial("Événement tardif")
        await engine._write_notes()
        assert work.cancelled()
        assert engine.state.consent_at is None and not engine.state.partial
        engine.coordinator.write_notes.assert_not_called()
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_old_session_keeps_evidence_and_opens_without_capture(tmp_path):
    store = SQLiteStore(tmp_path / "migration.sqlite3")
    engine, _ = make_engine(store)
    await engine.start()
    try:
        legacy = QuorumyState(
            project_id="quorumy",
            protocol_version=9,
            session_id="old",
            title="Titre choisi",
            title_locked=True,
            notes="# Notes antérieures",
            transcript=[
                Utterance(text="Prototype", speaker="Loutre", participant_id="loutre")
            ],
        ).model_dump(mode="json")
        legacy.pop("identity_name")
        legacy["assistant_name"] = "Quorumy"
        legacy.pop("notes_document")
        legacy["minutes"] = {"version": "keep", "notes": [], "stale": False}
        await store._db.execute(
            "INSERT INTO sessions(session_id, payload) VALUES(?, ?)",
            ("old", json.dumps(legacy)),
        )
        await store._db.commit()
        assert await engine.open_session("old")
        assert engine.state.notes == "# Notes antérieures"
        assert engine.state.notes_document.synthesis == ["# Notes antérieures"]
        assert engine.state.minutes["version"] == "keep"
        assert engine.state.transcript[0].participant_id == "loutre"
        assert (
            engine.state.identity_name == "Quorumy"
            and engine.state.protocol_version == 14
        )
        assert engine.state.session_status == SessionStatus.PAUSED
        assert not engine.state.consent_at and engine.stt.starts == 0
        assert engine.state.title == "Titre choisi" and engine.state.title_locked
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_transcript_survives_500_turns_and_delete_cascades(tmp_path):
    store = SQLiteStore(tmp_path / "long.sqlite3")
    engine, _ = make_engine(store)
    await engine.start()
    try:
        await engine.start_session({"capture_mode": "text", "consent": True})
        engine.state.title_locked = True
        engine._process_turn = AsyncMock()
        engine.state.transcript = [Utterance(text=f"Tour {i}") for i in range(505)]
        await engine.commit_utterance("Dernier tour", "manual")
        await engine.drain()
        sid = engine.state.session_id
        assert len((await store.load(sid)).transcript) == 506
        assert (
            len([e for e in await store.journal(sid) if e["kind"] == "utterance"])
            == 506
        )
        await engine.delete_session(sid)
        assert await store.load(sid) is None and await store.journal(sid) == []
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_reviewed_minutes_stale_after_new_utterance(tmp_path):
    engine, _ = make_engine(SQLiteStore(tmp_path / "minutes.sqlite3"))
    await engine.start()
    try:
        await engine.start_session({"capture_mode": "text", "consent": True})
        await engine.commit_utterance("Je prépare le prototype.", "manual")
        await engine.drain()
        board = await engine.generate_minutes()
        review = Review(
            type="minutes_review",
            version=board["version"],
            note_id=board["notes"][0]["id"],
            status="confirmed",
            owner_id="renard",
        )
        await engine.review_minutes(review)
        assert board["notes"][0]["status"] == "confirmed"
        await engine.commit_utterance("Le prototype attendra.", "manual")
        assert board["stale"]
        with pytest.raises(ValueError):
            await engine.review_minutes(review)
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_user_title_wins_over_inflight_automatic_name(tmp_path):
    engine, _ = make_engine(SQLiteStore(tmp_path / "name.sqlite3"))
    await engine.start()
    try:
        await engine.start_session({"capture_mode": "text", "consent": True})
        engine.state.transcript.append(Utterance(text="Une idée"))
        ready, release = asyncio.Event(), asyncio.Event()

        async def delayed(_):
            ready.set()
            await release.wait()
            return "Titre automatique"

        engine.coordinator.name_session = delayed
        task = engine._spawn(engine._rename_session())
        await ready.wait()
        await engine.rename_session(engine.state.session_id, "Mon titre")
        release.set()
        await task
        assert engine.state.title == "Mon titre"
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_muting_voice_keeps_a_direct_written_answer(tmp_path):
    from quorumy.workspace.core.models import SpeechPlan

    engine, published = make_engine(
        SQLiteStore(tmp_path / "silent.sqlite3"),
        decision=FakeDecision("respond", addressed=True),
    )
    await engine.start()
    try:
        await engine.start_session({"capture_mode": "text", "consent": True})
        await engine.set_voice_mode("muted")
        engine.speaker.answer = AsyncMock(
            return_value=SpeechPlan(
                speak=True, spoken_core="Le prototype reste à vérifier."
            )
        )
        await engine.commit_utterance("Quorumy, que reste-t-il à faire ?", "manual")
        await engine.drain()
        assert any(
            s.text == "Le prototype reste à vérifier." for s in engine.state.speeches
        )
        assert not any(event["type"] == "speech.audio.chunk" for event in published)
    finally:
        await engine.stop()


async def test_audio_echo_does_not_pollute_memory_or_invalidate_minutes(tmp_path):
    from quorumy.workspace.core.models import Speech
    from tests.workspace.test_echo import REPLY

    engine, _ = make_engine(SQLiteStore(tmp_path / "echo.sqlite3"))
    await engine.start()
    try:
        await engine.start_session({"capture_mode": "text", "consent": True})
        engine.state.speeches.append(
            Speech(text=REPLY, reason="direct_address", status="authorized")
        )
        speech = engine.state.speeches[-1]
        await engine.playback_changed(speech.id, "started")
        await engine.playback_changed(speech.id, "finished")
        engine.state.minutes = {"stale": False}
        await engine.commit_utterance(REPLY, "audio")
        assert not engine.state.transcript
        assert not engine.state.minutes["stale"]
        assert not engine.state.tasks
        assert engine.state.activities[-1].kind == "audio.echo_filtered"
        await engine.commit_utterance(REPLY, "manual")
        assert len(engine.state.transcript) == 1
        assert engine.state.minutes["stale"]
    finally:
        await engine.stop()


async def test_task_report_rechecks_context_after_human_correction(tmp_path):
    from quorumy.workspace.core.models import SpeechPlan, Task

    engine, _ = make_engine(SQLiteStore(tmp_path / "report.sqlite3"))
    await engine.start()
    try:
        await engine.start_session({"capture_mode": "text", "consent": True})
        calls = []

        async def report(state, task):
            calls.append(state.room_epoch)
            if len(calls) == 1:
                engine.state.room_epoch += 1
                return SpeechPlan(speak=True, spoken_core="Ancienne proposition")
            return SpeechPlan(speak=True, spoken_core="Proposition corrigée")

        engine.speaker.report_task = report
        engine._offer_speaker_text = AsyncMock()
        task = Task(tool="research_web", summary="Comparaison", status="done")
        await engine._speaker_task(task, engine.state.session_id)
        assert len(calls) == 2
        engine._offer_speaker_text.assert_awaited_once_with(
            "Proposition corrigée", "requested_result", [task.id]
        )
    finally:
        await engine.stop()
