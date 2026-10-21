from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Literal

from quorumy.workspace.config import PolicyConfig

from .models import Decision, Speech


@dataclass
class SpeechGate:
    policy: PolicyConfig
    _last_proactive_at: float | None = None
    _last_text: str = ""

    @staticmethod
    def response_reason(
        decision: Decision,
    ) -> Literal["direct_address"] | None:
        if decision.speech_depth == "silent":
            return None
        if (
            decision.route in {"respond", "control"}
            and decision.addressee == "quorumy"
            and decision.timing == "next_gap"
        ):
            return "direct_address"
        return None

    @staticmethod
    def hand_level(decision: Decision) -> Literal["raised", "urgent"] | None:
        if decision.signal == "urgent":
            return "urgent"
        if decision.signal == "raise":
            return "raised"
        if (
            decision.route == "respond"
            and decision.addressee == "room"
            and decision.initiative == "proactive"
            and decision.timing == "later"
            and decision.speech_depth != "silent"
        ):
            return "raised"
        return None

    def validate(self, speech: Speech) -> str | None:
        text = " ".join(speech.text.split()).strip()
        if not text:
            return "empty"
        if text.casefold() == self._last_text.casefold():
            return "duplicate"
        speech.text = text
        if (
            speech.reason in {"critical_finding", "awaited_response"}
            and self._last_proactive_at is not None
        ):
            elapsed = monotonic() - self._last_proactive_at
            if elapsed < self.policy.unsolicited_speech_cooldown_seconds:
                return "proactive_cooldown"
        return None

    def delivered(self, speech: Speech) -> None:
        self._last_text = speech.text
        if speech.reason in {"critical_finding", "awaited_response"}:
            self._last_proactive_at = monotonic()
