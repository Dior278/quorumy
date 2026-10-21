"""Opt-in live smoke check: synthetic text, real configured providers, isolated DB.

This script consumes provider credits. It never records a microphone.
"""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from quorumy.workspace.api.app import compose
from quorumy.workspace.api.hub import WebSocketHub
from quorumy.workspace.config import load_config, load_product


async def main():
    Path("tmp").mkdir(exist_ok=True)
    config = load_config()
    config.storage.database_path = str(
        Path("tmp") / f"workspace-live-{uuid4().hex}.sqlite3"
    )
    resources = compose(load_product(), config, WebSocketHub())
    engine = resources.engine
    await engine.start()
    try:
        await engine.start_session(
            {"capture_mode": "text", "consent": True, "language": "fr"}
        )
        await engine.set_voice_mode("muted")
        await engine.commit_utterance(
            "Je préparerai le prototype pour la démonstration. Nous retenons une interface en français et une mémoire locale.",
            "manual",
        )
        await asyncio.wait_for(engine.drain(), timeout=100)
        await engine._write_notes()
        assert engine.state.notes, "No synthesis produced"
        assert engine.state.notes_cursor == len(engine.state.transcript)
        board = await engine.generate_minutes()
        assert board["notes"], "No evidence-backed proposal produced"
        for note in board["notes"]:
            assert all(e["quote"] in e["text"] for e in note["evidence"])
        await engine.commit_utterance(
            "Quorumy, recherche sur le web la documentation officielle de WebRTC et conserve la source pour notre équipe.",
            "manual",
        )
        await asyncio.wait_for(engine.drain(), timeout=150)
        done = [t for t in engine.state.tasks if t.status == "done"]
        assert done, "No successful research tool call"
        assert any(t.result and t.result.get("results") for t in done), (
            "No research source returned"
        )
        request_id = engine.state.transcript[-1].id
        assert any(t.source_utterance_id == request_id for t in done)
        assert all(t.duration_ms is not None for t in done)
        task_ids = {t.id for t in done}
        grounded_replies = [
            speech
            for speech in engine.state.speeches
            if speech.reason == "requested_result"
            and task_ids.intersection(speech.source_ids)
            and speech.status == "suppressed"
            and speech.error == "voice_muted"
        ]
        assert grounded_replies, "No written answer linked to the research result"
        assert engine.state.minutes["stale"]
        await engine.session_command("pause")
        restored = await engine.store.load(engine.state.session_id)
        assert len(restored.transcript) == 2
        report = {
            "synthesis": True,
            "verified_proposals": len(board["notes"]),
            "successful_tools": [t.tool for t in done],
            "restart_snapshot": True,
            "capture": "text only",
            "voice": "muted",
            "answers_linked_to_research": len(grounded_replies),
            "mission_duration_ms": [t.duration_ms for t in done],
        }
        Path("tmp/workspace-live-validation.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report))
    finally:
        await engine.stop()
        await engine.backend.close()


if __name__ == "__main__":
    asyncio.run(main())
