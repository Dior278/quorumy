"""One real, billable structured extraction on a fictional discussion."""

import asyncio

from quorumy.minutes import build_minutes
from quorumy.providers import LiveBackend
from quorumy.settings import AppSettings


async def main():
    backend = LiveBackend(AppSettings())
    utterances = [
        {
            "utterance_id": "u1",
            "participant_id": "renard",
            "speaker": "You",
            "at": "2026-09-26T10:00:00Z",
            "text": "I will prepare the prototype on Friday, without starting production.",
        },
        {
            "utterance_id": "u2",
            "participant_id": "hibou",
            "speaker": "Owl",
            "at": "2026-09-26T10:01:00Z",
            "text": "We are keeping the local prototype for the demonstration. The budget is still open.",
        },
        {
            "utterance_id": "u3",
            "participant_id": "renard",
            "speaker": "You",
            "at": "2026-09-26T10:02:00Z",
            "text": "Correction: I am no longer promising Friday. The date depends on the audio test.",
        },
    ]
    try:
        result = await backend.meeting_minutes(utterances)
        board = build_minutes(result, utterances)
        assert board["notes"], "No grounded note returned"
        assert not board["discarded"], "At least one citation was rejected"
        assert all(note["status"] == "proposed" for note in board["notes"])
        print(
            f"PASS: real extraction, {len(board['notes'])} proposals with exact citations; all require human review."
        )
        for note in board["notes"]:
            print(
                f"  {note['kind']}: {note['text']} (due quote: {note['due_quote'] or 'none'})"
            )
        print(
            "Synthetic content only. Exact citations do not prove semantic correctness."
        )
    finally:
        await backend.close()


if __name__ == "__main__":
    asyncio.run(main())
