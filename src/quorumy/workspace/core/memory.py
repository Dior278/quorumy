"""Confirmed commitments that follow a team from one meeting to the next."""

from __future__ import annotations

import re
import unicodedata

from quorumy.workspace.core.models import CarriedCommitment, QuorumyState

_STOP = frozenset(
    """
    about après alors aussi autre autres avoir avec cette cet cette ceux cette
    comme dans des dont elle elles encore entre etait était fait faire faut
    leur leurs mais même meme nous parce plus pour quoi sans sont sous cette
    tout tous tout très tres vous votre votre cette this that with from they
    have been were will your their there would could should about
    """.split()
)
_REVERSAL = re.compile(
    r"\b(plus|contraire|annule|annulee|annulée|finalement|incoherent|incohérence|contredit|faux)\b",
    re.IGNORECASE,
)


def carry_forward(
    states: list[QuorumyState], exclude_session_id: str | None
) -> list[CarriedCommitment]:
    ordered = sorted(states, key=lambda item: item.updated_at, reverse=True)
    carried: list[CarriedCommitment] = []
    seen: set[tuple[str, str]] = set()
    for state in ordered:
        if not state.session_id or state.session_id == exclude_session_id:
            continue
        for item in confirmed_open(state):
            key = (item.session_id, item.id)
            if key in seen:
                continue
            seen.add(key)
            carried.append(item)
            if len(carried) == 12:
                return carried
    return carried


def confirmed_open(state: QuorumyState) -> list[CarriedCommitment]:
    minutes = state.minutes or {}
    notes = minutes.get("notes")
    if not isinstance(notes, list) or not state.session_id:
        return []
    items: list[CarriedCommitment] = []
    for note in notes:
        if not isinstance(note, dict) or note.get("status") != "confirmed":
            continue
        kind = note.get("kind")
        text = str(note.get("text") or "").strip()
        if kind not in {"decision", "action", "question", "risk"} or not text:
            continue
        due = note.get("due_date")
        items.append(
            CarriedCommitment(
                id=str(note.get("id") or ""),
                session_id=state.session_id,
                session_title=state.title,
                kind=kind,
                text=text,
                owner_name=str(note.get("owner_name") or ""),
                due_date=str(due) if due else None,
            )
        )
    return items


def open_commitment_count(state: QuorumyState) -> int:
    return len(confirmed_open(state))


def commitment_conflict(
    utterance: str, carried: list[CarriedCommitment]
) -> CarriedCommitment | None:
    words = _words(utterance)
    spoken_amounts = _amounts(utterance)
    reversal = bool(_REVERSAL.search(_fold(utterance)))
    best: CarriedCommitment | None = None
    best_score = 0
    for item in carried:
        if item.status != "open":
            continue
        shared = words & _words(item.text)
        if not shared:
            continue
        remembered = _amounts(item.text)
        number_clash = bool(
            spoken_amounts and remembered and spoken_amounts.isdisjoint(remembered)
        )
        if number_clash or (reversal and len(shared) >= 2):
            score = len(shared) + (2 if number_clash else 0)
            if score > best_score:
                best, best_score = item, score
    return best


def meeting_conflict(utterance: str, earlier: list[str]) -> bool:
    if explicit_contradiction(utterance):
        return True
    spoken_amounts = _amounts(utterance)
    words = _words(utterance)
    if not spoken_amounts or not words:
        return False
    for line in earlier:
        if (
            words & _words(line)
            and _amounts(line)
            and spoken_amounts.isdisjoint(_amounts(line))
        ):
            return True
    return False


def explicit_contradiction(text: str) -> bool:
    folded = _fold(text)
    return any(
        marker in folded
        for marker in (
            "incoherence",
            "contradiction",
            "ne correspond",
            "pas le meme",
            "c'est faux",
            "cest faux",
            "contredit",
        )
    )


def reminder(item: CarriedCommitment, language: str) -> str:
    if language == "en":
        who = (
            f"{item.owner_name} had committed to this"
            if item.owner_name
            else "This was confirmed"
        )
        return (
            f"{who}: {item.text}. What was just said no longer matches. "
            f"It comes from {item.session_title}."
        )
    who = f"{item.owner_name} s’était engagé" if item.owner_name else "C’était confirmé"
    return (
        f"{who} : {item.text}. Ce qui vient d’être dit ne correspond plus. "
        f"Cela vient de {item.session_title}."
    )


def _fold(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(char) != "Mn"
    )


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z]{5,}", _fold(text)) if word not in _STOP}


def _amounts(text: str) -> set[str]:
    compact = re.sub(r"(?<=\d)[\s\u00a0](?=\d)", "", text)
    found = re.findall(r"\d+(?:[.,]\d+)*", compact)
    amounts: set[str] = set()
    for item in found:
        digits = re.sub(r"[.,]", "", item).lstrip("0")
        if digits:
            amounts.add(digits)
    return amounts
