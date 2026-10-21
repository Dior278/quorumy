import pytest

from quorumy.minutes import Evidence, ProposedMinutes, ProposedNote, build_minutes


@pytest.mark.parametrize("changed", [False, True])
def test_refresh_preserves_only_identical_reviewed_notes(changed):
    utterance = {
        "utterance_id": "u1",
        "participant_id": "alice",
        "speaker": "Alice",
        "text": "Je prépare le prototype vendredi.",
        "at": "2026-09-26T10:00:00Z",
    }
    proposal = ProposedMinutes(
        notes=[
            ProposedNote(
                kind="action",
                text="Préparer le prototype.",
                evidence=[Evidence(utterance_id="u1", quote=utterance["text"])],
                owner_id="alice",
                due_quote="vendredi",
            )
        ]
    )
    previous = build_minutes(proposal, [utterance])
    note = previous["notes"][0]
    note.update(
        status="confirmed",
        due_date="2026-10-02",
        reviewed_by="Alice",
        reviewed_at="2026-09-26T10:01:00Z",
    )
    previous["stale"] = True
    if changed:
        proposal.notes[0].text = "Tester le prototype avant de le préparer."
    refreshed = build_minutes(proposal, [utterance], previous=previous)
    current = refreshed["notes"][0]
    assert refreshed["version"] != previous["version"]
    assert current["status"] == ("proposed" if changed else "confirmed")
    assert current["due_date"] == (None if changed else "2026-10-02")
    assert (current["id"] == note["id"]) is (not changed)


def test_a_changed_source_invalidates_review_even_with_identical_summary():
    utterance = {
        "utterance_id": "u1",
        "participant_id": "alice",
        "speaker": "Alice",
        "text": "Je prépare le prototype vendredi.",
        "at": "2026-09-26T10:00:00Z",
    }
    note = ProposedNote(
        kind="action",
        text="Préparer le prototype.",
        evidence=[Evidence(utterance_id="u1", quote=utterance["text"])],
        owner_id="alice",
        due_quote="vendredi",
    )
    previous = build_minutes(ProposedMinutes(notes=[note]), [utterance])
    previous["notes"][0].update(status="confirmed", due_date="2026-10-02")
    correction = {
        **utterance,
        "utterance_id": "u2",
        "text": "Finalement le prototype attendra lundi.",
    }
    updated = note.model_copy(
        update={
            "evidence": [Evidence(utterance_id="u2", quote=correction["text"])],
            "due_quote": "lundi",
        }
    )
    result = build_minutes(
        ProposedMinutes(notes=[updated]), [utterance, correction], previous
    )
    assert result["notes"][0]["status"] == "proposed"
    assert result["notes"][0]["due_date"] is None
