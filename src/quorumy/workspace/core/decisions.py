from __future__ import annotations

from .models import Decision, QuorumyState


def conservative_fallback(state: QuorumyState, text: str) -> Decision:
    del state, text
    return Decision(
        route="capture",
        addressee="uncertain",
        memory="capture",
        rationale="Semantic decision service unavailable; Quorumy records context without guessing intent.",
    )
