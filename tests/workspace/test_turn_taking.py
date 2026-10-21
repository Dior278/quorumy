"""Conversation timing regressions; synthetic providers, no captured meetings."""

from __future__ import annotations

import asyncio

import pytest

from quorumy.workspace.core.models import Decision, Speech
from quorumy.workspace.core.speech import SpeechGate
from tests.workspace.test_engine import (
    FakeDecision,
    FakeGenerator,
    FakeTTS,
    SequenceDecision,
    build_engine,
)


class DelayedTTS(FakeTTS):
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.stopped = asyncio.Event()

    async def stream_chunks(self, text_chunks, language, on_chunk, on_text=None):
        try:
            async for _ in text_chunks:
                self.started.set()
                await self.release.wait()
                await on_chunk(b"\0\0", 24000, "pcm_24000")
        finally:
            self.stopped.set()


def fast_policy(engine):
    engine.config.policy.direct_floor_gap_seconds = 0.02
    engine.config.policy.stable_floor_gap_seconds = 0.04


@pytest.mark.asyncio
async def test_result_waits_for_a_fresh_gap_when_human_speaks_during_tts():
    messages = []
    tts = DelayedTTS()
    engine = build_engine(FakeDecision(), FakeGenerator(), messages, tts)
    fast_policy(engine)
    await engine.start()
    await engine.start_session({})
    speech = Speech(text="Voici le résultat.", reason="requested_result")
    job = asyncio.create_task(engine._deliver(speech))
    try:
        await asyncio.wait_for(tts.started.wait(), 1)
        await engine.floor_changed(True)
        tts.release.set()
        await asyncio.sleep(0.07)
        assert not any(m.get("type") == "speech.authorized" for m in messages)
        await engine.floor_changed(False)
        await asyncio.sleep(0.01)
        assert not any(m.get("type") == "speech.authorized" for m in messages)
        await asyncio.wait_for(job, 1)
        assert speech.status == "authorized"
    finally:
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)
        await engine.stop()


class ContinuingTTS(FakeTTS):
    def __init__(self):
        self.stopped = asyncio.Event()

    async def stream_chunks(self, text_chunks, language, on_chunk, on_text=None):
        try:
            async for _ in text_chunks:
                await on_chunk(b"\0\0", 24000, "pcm_24000")
                await asyncio.Event().wait()
        finally:
            self.stopped.set()


@pytest.mark.asyncio
async def test_barge_in_stops_result_generation_and_late_playback_cannot_revive_it():
    messages = []
    tts = ContinuingTTS()
    engine = build_engine(FakeDecision(), FakeGenerator(), messages, tts)
    fast_policy(engine)
    await engine.start()
    await engine.start_session({})
    try:
        await engine._offer_speaker_text("Résultat prêt.", "requested_result", [])
        async with asyncio.timeout(1):
            while not engine._active_speech_id:
                await asyncio.sleep(0.005)
        speech = engine.state.speeches[-1]
        await engine.floor_changed(True)
        assert speech.status == "interrupted"
        assert tts.stopped.is_set()
        assert engine._playback_idle.is_set()
        await engine.playback_changed(speech.id, "started")
        await engine.playback_changed(speech.id, "finished")
        assert speech.status == "interrupted"
        assert any(m.get("type") == "speech.stop" for m in messages)
    finally:
        await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "addressee,timing",
    [("room", "next_gap"), ("quorumy", "silent"), ("quorumy", "later")],
)
async def test_room_questions_and_deferred_answers_do_not_trigger_voice(
    addressee, timing
):
    messages = []
    decision = SequenceDecision(
        [
            Decision(
                route="respond",
                addressee=addressee,
                timing=timing,
                speech_depth="normal",
            )
        ]
    )
    engine = build_engine(decision, FakeGenerator(), messages)
    await engine.start()
    await engine.start_session({})
    try:
        await engine.commit_utterance(
            "Comment allons-nous résoudre ce problème ?", source="manual"
        )
        await engine.drain()
        assert not any(m.get("type") == "speech.authorized" for m in messages)
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_short_silences_never_bypass_the_configured_gap(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("quorumy.workspace.core.engine.monotonic", lambda: clock[0])
    engine = build_engine(FakeDecision(), FakeGenerator(), [])
    await engine.start()
    await engine.start_session({})
    speech = Speech(text="Une proposition.", reason="requested_result")
    job = asyncio.create_task(
        engine._wait_for_speech_gap(speech, engine.state.session_id)
    )
    try:
        for second in range(1, 6):
            clock[0] = 100.0 + second
            await engine.floor_changed(True)
            await engine.floor_changed(False)
            clock[0] += 0.1
            await asyncio.sleep(0)
            assert not job.done()
        clock[0] += engine.config.policy.stable_floor_gap_seconds
        engine._floor_changed_event.set()
        assert await asyncio.wait_for(job, 1)
    finally:
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)
        await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("human_resumes", [False, True])
async def test_uninvited_help_raises_a_hand_instead_of_speaking(
    monkeypatch, human_resumes
):
    clock = [100.0]
    monkeypatch.setattr("quorumy.workspace.core.engine.monotonic", lambda: clock[0])
    monkeypatch.setattr("quorumy.workspace.core.speech.monotonic", lambda: clock[0])
    messages = []
    decision = SequenceDecision(
        [
            Decision(
                route="respond",
                addressee="room",
                initiative="proactive",
                speech_depth="normal",
                timing="later",
            )
        ]
    )
    engine = build_engine(decision, FakeGenerator(), messages)
    await engine.start()
    await engine.start_session({})
    try:
        await engine.floor_changed(True)
        await engine.commit_utterance(
            "On attend une piste pour débloquer ce problème.", source="manual"
        )
        async with asyncio.timeout(1):
            while engine.state.hand.level == "idle":
                await asyncio.sleep(0)
        await engine.floor_changed(False)
        clock[0] += 2.9
        engine._floor_changed_event.set()
        await asyncio.sleep(0.02)
        if human_resumes:
            await engine.floor_changed(True)
        clock[0] += 0.2
        engine._floor_changed_event.set()
        await asyncio.wait_for(engine.drain(), 1)
        assert not any(m.get("type") == "speech.authorized" for m in messages)
        assert engine.state.hand.level == "raised"
        assert engine.state.hand.pending_text
        assert not any(m.get("type") == "presence.cue" for m in messages)
    finally:
        await engine.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("invited", [False, True])
async def test_cooldown_limits_unsolicited_help_but_allows_an_invitation(invited):
    messages = []
    decision = SequenceDecision(
        [
            Decision(
                route="respond",
                addressee="quorumy" if invited else "room",
                initiative="assigned" if invited else "proactive",
                speech_depth="brief",
                timing="next_gap" if invited else "later",
            )
        ]
    )
    engine = build_engine(decision, FakeGenerator(), messages)
    fast_policy(engine)
    await engine.start()
    await engine.start_session({})
    engine._gate.delivered(
        Speech(text="Une précédente suggestion.", reason="awaited_response")
    )
    try:
        await engine.commit_utterance(
            "Quorumy, à toi." if invited else "On attend encore une piste.",
            source="manual",
        )
        await asyncio.wait_for(engine.drain(), 1)
        offered = [m for m in messages if m.get("type") == "speech.authorized"]
        assert bool(offered) == invited
        if not invited:
            assert engine.state.hand.level == "raised"
            assert not engine.state.speeches
    finally:
        await engine.stop()


def test_an_unaddressed_question_does_not_by_itself_grant_the_floor():
    for addressee, initiative, timing in [
        ("room", "none", "later"),
        ("room", "proactive", "next_gap"),
        ("another_participant", "proactive", "later"),
        ("uncertain", "proactive", "later"),
    ]:
        assert (
            SpeechGate.response_reason(
                Decision(
                    route="respond",
                    addressee=addressee,
                    initiative=initiative,
                    timing=timing,
                    speech_depth="brief",
                )
            )
            is None
        )
