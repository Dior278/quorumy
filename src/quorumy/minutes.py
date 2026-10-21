"""Evidence-linked meeting notes. Models propose; people confirm commitments."""

import hashlib
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    utterance_id: str
    quote: str = Field(min_length=12, max_length=3000)


class ProposedNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["decision", "action", "question", "risk"]
    text: str = Field(min_length=1, max_length=600)
    evidence: list[Evidence] = Field(min_length=1, max_length=4)
    owner_id: str | None
    due_quote: str | None


class ProposedMinutes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notes: list[ProposedNote] = Field(max_length=12)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["minutes_review"]
    version: str
    note_id: str
    status: Literal["confirmed", "rejected", "proposed"]
    owner_id: str = Field(default="", max_length=100)
    due_date: date | None = None


def build_minutes(
    proposal: ProposedMinutes, utterances: list[dict], previous: dict | None = None
) -> dict:
    """Reject fabricated references; an exact quote is not semantic verification."""
    by_id = {u["utterance_id"]: u for u in utterances}
    speakers = {u.get("participant_id"): u["speaker"] for u in utterances}
    notes, discarded, fingerprints = [], 0, set()
    previous_notes = {
        n.get("fingerprint"): n
        for n in (previous or {}).get("notes", [])
        if n.get("fingerprint")
    }
    for candidate in proposal.notes:
        evidence = []
        for citation in candidate.evidence:
            original = by_id.get(citation.utterance_id)
            if not original or citation.quote not in original["text"]:
                break
            evidence.append({**original, "quote": citation.quote})
        if len(evidence) != len(candidate.evidence):
            discarded += 1
            continue
        fingerprint = hashlib.sha256(
            json.dumps(
                [
                    candidate.kind,
                    candidate.text,
                    sorted((e["utterance_id"], e["quote"]) for e in evidence),
                    candidate.owner_id,
                    candidate.due_quote,
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        owner_id = candidate.owner_id if candidate.owner_id in speakers else ""
        due = candidate.due_quote
        if due and not any(due in e["text"] for e in evidence):
            due = None
        notes.append(
            {
                "id": secrets.token_urlsafe(8),
                "fingerprint": fingerprint,
                "kind": candidate.kind,
                "text": candidate.text,
                "evidence": evidence,
                "status": "proposed",
                "owner_id": owner_id or "",
                "owner_name": speakers.get(owner_id, ""),
                "due_quote": due,
                "due_date": None,
                "reviewed_by": None,
                "reviewed_at": None,
            }
        )
        old = previous_notes.get(fingerprint)
        if old:
            for key in (
                "id",
                "status",
                "owner_id",
                "owner_name",
                "due_date",
                "reviewed_by",
                "reviewed_at",
            ):
                notes[-1][key] = old[key]
    return {
        "version": secrets.token_urlsafe(12),
        "revision": len(utterances),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
        "discarded": discarded,
        "stale": False,
    }


LABELS = {
    "decision": "Decision",
    "action": "Action",
    "question": "Question",
    "risk": "Risk",
}


def markdown_export(board: dict, objective: str) -> str:
    # Escape Markdown syntax from untrusted meeting text, including autolinks.
    def plain(value):
        value = str(value).replace("\r", " ").replace("\n", " ")
        for char in "\\`*_{}[]<>()#+-.!|":
            value = value.replace(char, "\\" + char)
        return value

    lines = [
        "# Quorumy — meeting record",
        "",
        plain(objective or "Discussion"),
        "",
        "AI proposals reviewed by participants. Quotes do not guarantee the interpretation.",
        "Statuses and owners are declarative; first names are not verified identities.",
        "",
    ]
    for note in board["notes"]:
        if note["status"] == "rejected":
            continue
        status = "Confirmed" if note["status"] == "confirmed" else "To review"
        lines += [f"## {LABELS[note['kind']]} · {status}", "", plain(note["text"])]
        if note["kind"] == "action":
            lines += [
                f"Owner: {plain(note['owner_name'] or 'unassigned')}",
                f"Confirmed due date: {note['due_date'] or 'not set'}",
            ]
        if note["reviewed_by"]:
            lines += [f"Review: {plain(note['reviewed_by'])} · {note['reviewed_at']}"]
        for evidence in note["evidence"]:
            lines += [
                f"> {plain(evidence['speaker'])} · {evidence['at']} · {evidence['utterance_id']} : {plain(evidence['text'])}"
            ]
        lines.append("")
    return "\n".join(lines)


def calendar_export(board: dict, room_id: str) -> str:
    """Portable all-day reminders, never invitations or invented meeting times."""

    def escape(value):
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("\r", "")
            .replace("\n", "\\n")
            .replace(";", "\\;")
            .replace(",", "\\,")
        )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Quorumy//Meeting actions//EN",
        "CALSCALE:GREGORIAN",
    ]
    for note in board["notes"]:
        if (
            note["kind"] != "action"
            or note["status"] != "confirmed"
            or not note["due_date"]
            or not note["owner_id"]
        ):
            continue
        due = date.fromisoformat(note["due_date"])
        lines += [
            "BEGIN:VEVENT",
            f"UID:{room_id}-{note['id']}@quorumy.local",
            "DTSTAMP:" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "DTSTART;VALUE=DATE:" + due.strftime("%Y%m%d"),
            "DTEND;VALUE=DATE:" + (due + timedelta(days=1)).strftime("%Y%m%d"),
            "SUMMARY:" + escape(note["text"]),
            "DESCRIPTION:"
            + escape(
                f"Owner: {note['owner_name']}\nConfirmed by: {note['reviewed_by']}\nQuorumy reminder, not an automatic invitation."
            ),
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    if "BEGIN:VEVENT" not in lines:
        raise ValueError(
            "Confirm an action with an owner and a date before exporting the calendar."
        )
    lines.append("END:VCALENDAR")
    # RFC 5545: fold at 75 octets without splitting a UTF-8 codepoint.
    folded = []
    for line in lines:
        part = ""
        for char in line:
            if len((part + char).encode("utf-8")) > 75:
                folded.append(part)
                part = " "
            part += char
        folded.append(part)
    return "\r\n".join(folded) + "\r\n"
