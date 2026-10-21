"""Conservative text guard for recently played Quorumy audio returning through STT.

This is a second guard, not acoustic echo cancellation. Only a long exact word
sequence at the edges is removed; novel speech and internal quotations survive.
"""

import re
import unicodedata
from datetime import UTC, datetime
from difflib import SequenceMatcher

from quorumy.workspace.core.models import Speech

WORD = re.compile(r"\w+", re.UNICODE)


def words(text: str):
    return [
        (
            "".join(
                c
                for c in unicodedata.normalize("NFD", m.group().lower())
                if unicodedata.category(c) != "Mn"
            ),
            m.start(),
            m.end(),
        )
        for m in WORD.finditer(text)
    ]


def remove_playback_echo(text: str, speeches: list[Speech], *, now=None) -> str:
    now = now or datetime.now(UTC)
    tokens = words(text)
    if len(tokens) < 8 or any(mark in text for mark in ("«", "»", "“", "”", '"')):
        return text
    for speech in reversed(speeches[-8:]):
        if not speech.playback_started_at:
            continue
        end = speech.playback_ended_at
        try:
            reference = datetime.fromisoformat(end or speech.playback_started_at)
            age = (now - reference).total_seconds()
        except (ValueError, TypeError):
            continue
        if not 0 <= age <= (12 if end else 120):
            continue
        own = [word[0] for word in words(speech.text)]
        incoming = [word[0] for word in tokens]
        match = SequenceMatcher(
            None, incoming, own, autojunk=False
        ).find_longest_match()
        if match.size < 8:
            continue
        # Match punctuation/accent variations, never approximate a changed number
        # or a negation. Preserve corrections surrounding a quoted response.
        if match.a == 0 and match.size == len(incoming):
            return ""
        if match.size != len(own) or len(incoming) - match.size < 4:
            continue
        if match.a == 0:
            return text[tokens[match.size - 1][2] :].lstrip(" ,.;:!?—-\n")
        if match.a + match.size == len(incoming):
            return text[: tokens[match.a][1]].rstrip()
    return text
