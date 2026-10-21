import asyncio

import pytest

from quorumy.minutes import (
    Evidence,
    ProposedMinutes,
    ProposedNote,
    build_minutes,
    calendar_export,
    markdown_export,
)
from quorumy.providers import LiveBackend, ProviderError
from quorumy.settings import AppSettings

UTTERANCES = [
    {
        "utterance_id": "u1",
        "participant_id": "alice",
        "speaker": "Alice",
        "text": "Je prépare le prototype vendredi, sans lancer la production.",
        "at": "2026-09-26T10:00:00+00:00",
    }
]


def proposal(**overrides):
    values = dict(
        kind="action",
        text="Préparer le prototype.",
        evidence=[Evidence(utterance_id="u1", quote=UTTERANCES[0]["text"])],
        owner_id="alice",
        due_quote="vendredi",
    )
    return ProposedMinutes(notes=[ProposedNote(**{**values, **overrides})])


@pytest.mark.parametrize(
    "reference,quote",
    [("u999", UTTERANCES[0]["text"]), ("u1", "Nous lançons la production vendredi.")],
)
def test_rejects_invented_quotes_and_references(reference, quote):
    board = build_minutes(
        proposal(evidence=[Evidence(utterance_id=reference, quote=quote)]), UTTERANCES
    )
    assert board["notes"] == []
    assert board["discarded"] == 1


def test_citations_keep_full_context_and_never_auto_confirm():
    board = build_minutes(proposal(), UTTERANCES)
    note = board["notes"][0]
    assert note["status"] == "proposed"
    assert note["due_date"] is None
    assert "sans lancer" in note["evidence"][0]["text"]
    assert note["owner_name"] == "Alice"
    with pytest.raises(ValueError):
        calendar_export(board, "room")


def test_unknown_owner_and_unsourced_due_date_are_removed():
    note = build_minutes(proposal(owner_id="invented", due_quote="lundi"), UTTERANCES)[
        "notes"
    ][0]
    assert not note["owner_id"]
    assert not note["due_quote"]


def test_calendar_exports_only_complete_confirmed_actions_and_escapes_injection():
    board = build_minutes(
        proposal(text="Préparer, tester; " + "é" * 110 + "\nBEGIN:VEVENT"), UTTERANCES
    )
    note = board["notes"][0]
    note.update(status="confirmed", due_date="2026-12-31", reviewed_by="Alice")
    for changes in [
        {"status": "proposed"},
        {"status": "rejected"},
        {"kind": "decision"},
        {"due_date": None},
        {"owner_id": ""},
    ]:
        board["notes"].append({**note, **changes})
    result = calendar_export(board, "room")
    assert result.split("\r\n").count("BEGIN:VEVENT") == 1
    assert "DTSTART;VALUE=DATE:20261231" in result
    assert "DTEND;VALUE=DATE:20270101" in result
    assert "Préparer\\, tester\\;" in result
    assert all(len(line.encode()) <= 75 for line in result.split("\r\n"))
    assert "ATTENDEE" not in result and "METHOD:REQUEST" not in result
    assert "UID:room-" in result


def test_markdown_separates_proposals_and_escapes_active_content():
    board = build_minutes(
        proposal(text="<script>alert(1)</script> [lien](https://example.com)"),
        UTTERANCES,
    )
    board["notes"].append(
        {**board["notes"][0], "status": "rejected", "text": "ne pas exporter"}
    )
    output = markdown_export(board, "Exemple")
    assert "À vérifier" in output
    assert "<script>" not in output
    assert "[lien](" not in output
    assert "ne pas exporter" not in output
    assert "sans lancer" in output


@pytest.mark.parametrize("bad", [False, True])
def test_provider_uses_structured_schema_and_exposes_failure(bad):
    class MinutesGenerator:
        available = True

        async def generate(self, messages, model_id=None):
            assert "utterance_id" in messages[-1]["content"]
            from quorumy.workspace.core.models import LLMResult

            return LLMResult(
                content="{}" if bad else proposal().model_dump_json(),
                model="qwen",
                provider="huggingface",
            )

    async def scenario():
        backend = LiveBackend(AppSettings(_env_file=None), generator=MinutesGenerator())
        try:
            if bad:
                with pytest.raises(ProviderError):
                    await backend.meeting_minutes(UTTERANCES)
            else:
                assert (await backend.meeting_minutes(UTTERANCES)).notes[
                    0
                ].kind == "action"
        finally:
            await backend.close()

    asyncio.run(scenario())
