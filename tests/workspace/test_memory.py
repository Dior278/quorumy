from __future__ import annotations

import pytest

from quorumy.workspace.core.memory import (
    carry_forward,
    commitment_conflict,
    meeting_conflict,
)
from quorumy.workspace.core.models import QuorumyState
from tests.workspace.test_engine import (
    FakeDecision,
    FakeGenerator,
    MemoryStore,
    build_engine,
)


def _state(session_id: str, title: str, notes: list[dict]) -> QuorumyState:
    return QuorumyState(
        project_id="quorumy",
        protocol_version=14,
        session_id=session_id,
        title=title,
        minutes={"notes": notes},
    )


def test_only_confirmed_commitments_follow_the_team() -> None:
    previous = _state(
        "session-a",
        "Budget",
        [
            {
                "id": "keep",
                "kind": "action",
                "text": "Léa envoie le budget de 12 000 euros.",
                "status": "confirmed",
                "owner_name": "Léa",
            },
            {
                "id": "draft",
                "kind": "action",
                "text": "Proposition encore à relire par l’équipe.",
                "status": "proposed",
                "owner_name": "",
            },
            {
                "id": "closed",
                "kind": "action",
                "text": "Le compte rendu a déjà été envoyé.",
                "status": "done",
                "owner_name": "",
            },
        ],
    )
    carried = carry_forward([previous], "session-b")
    assert [item.id for item in carried] == ["keep"]
    assert commitment_conflict("On parle du planning de livraison.", carried) is None
    clash = commitment_conflict(
        "Le budget annoncé est maintenant de 9 000 euros.", carried
    )
    assert clash is not None and clash.id == "keep"
    assert meeting_conflict(
        "Le budget passe à 9 000.",
        ["Le budget validé est de 12 000 euros."],
    )


@pytest.mark.asyncio
async def test_a_new_meeting_raises_its_hand_on_a_broken_commitment() -> None:
    previous = _state(
        "session-a",
        "Budget",
        [
            {
                "id": "keep",
                "kind": "action",
                "text": "Léa envoie le budget de 12 000 euros.",
                "status": "confirmed",
                "owner_name": "Léa",
            }
        ],
    )
    store = MemoryStore()
    await store.save(previous)
    published: list[dict[str, object]] = []
    engine = build_engine(
        FakeDecision(route="capture", addressed=False),
        FakeGenerator(),
        published,
        store=store,
    )
    await engine.start()
    await engine.start_session({})
    assert engine.state.carried[0].text.startswith("Léa")
    await engine.commit_utterance(
        "Le budget annoncé est maintenant de 9 000 euros.", source="manual"
    )
    await engine.drain()
    assert engine.state.hand.level == "urgent"
    assert "12 000" in engine.state.hand.pending_text
    await engine.settle_commitment("session-a", "keep")
    assert engine.state.carried[0].status == "done"
    saved = await store.load("session-a")
    assert saved is not None
    assert saved.minutes["notes"][0]["status"] == "done"
    await engine.stop()


class _BrokenDecision:
    available = True

    async def evaluate(self, state: QuorumyState, text: str):
        raise RuntimeError("no credits")


@pytest.mark.asyncio
async def test_a_silent_model_still_raises_on_a_broken_commitment() -> None:
    previous = _state(
        "session-a",
        "Budget",
        [
            {
                "id": "keep",
                "kind": "action",
                "text": "Léa envoie le budget de 12 000 euros.",
                "status": "confirmed",
                "owner_name": "Léa",
            }
        ],
    )
    store = MemoryStore()
    await store.save(previous)
    engine = build_engine(_BrokenDecision(), FakeGenerator(), [], store=store)
    await engine.start()
    await engine.start_session({})
    await engine.commit_utterance(
        "Le budget annoncé est maintenant de 9 000 euros.", source="manual"
    )
    await engine.drain()
    assert engine.state.hand.level == "urgent"
    assert "12 000" in engine.state.hand.pending_text
    await engine.stop()
