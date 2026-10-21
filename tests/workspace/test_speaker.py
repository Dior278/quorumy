# pyright: reportPrivateUsage=false
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

import pytest

from quorumy.workspace.core.models import Decision, LLMResult, QuorumyState, Utterance
from quorumy.workspace.core.speaker import SpeakerAgent


class VerboseGenerator:
    available = True

    async def generate(
        self, messages: list[dict[str, str]], model_id: str | None = None
    ) -> LLMResult:
        return LLMResult(content="{}", model="test", provider="test")

    async def stream(
        self, messages: list[dict[str, str]], model_id: str | None = None
    ) -> AsyncIterator[str]:
        yield "First essential point. Second useful point. Third detail. Fourth detail."


class LongSentenceGenerator(VerboseGenerator):
    async def stream(
        self, messages: list[dict[str, str]], model_id: str | None = None
    ) -> AsyncIterator[str]:
        yield (
            "A long answer can contain substantial context and several clauses without becoming multiple "
            "spoken sentences, so Quorumy must wait for the actual semantic boundary before counting it. "
            "Second complete sentence. Third detail."
        )


@pytest.mark.asyncio
async def test_brief_speech_plan_emits_complete_bounded_turn() -> None:
    phrases: list[str] = []

    async def on_phrase(phrase: str) -> None:
        phrases.append(phrase)

    speaker = SpeakerAgent(VerboseGenerator())
    result = await speaker.stream_answer(
        QuorumyState(project_id="quorumy", protocol_version=1),
        Utterance(text="Quorumy, summarize."),
        Decision(
            route="respond",
            addressee="quorumy",
            speech_depth="brief",
            timing="next_gap",
        ),
        on_phrase,
    )
    assert phrases == ["First essential point.", "Second useful point."]
    assert result.spoken_core == "First essential point. Second useful point."


@pytest.mark.asyncio
async def test_long_sentence_is_never_split_by_character_count() -> None:
    phrases: list[str] = []

    async def on_phrase(phrase: str) -> None:
        phrases.append(phrase)

    speaker = SpeakerAgent(LongSentenceGenerator())
    result = await speaker.stream_answer(
        QuorumyState(project_id="quorumy", protocol_version=1),
        Utterance(text="Quorumy, explain this briefly."),
        Decision(
            route="respond",
            addressee="quorumy",
            speech_depth="brief",
            timing="next_gap",
        ),
        on_phrase,
    )
    assert len(phrases) == 2
    assert phrases[0].endswith("counting it.")
    assert "actual semantic boundary" in phrases[0]
    assert result.spoken_core.endswith("Second complete sentence.")


def test_compact_tool_projection_cannot_flood_speaker_context() -> None:
    projected = SpeakerAgent._compact_result(
        {
            "results": [
                {"title": "T" * 500, "highlights": ["H" * 2000, "ignored"]}
                for _ in range(8)
            ]
        }
    )
    assert projected is not None
    sources = cast(list[dict[str, object]], projected["sources"])
    assert len(sources) == 3
    assert all(len(str(source["title"])) <= 160 for source in sources)
    for source in sources:
        highlights = cast(list[object], source["highlights"])
        assert len(str(highlights[0])) <= 240


def test_research_projection_keeps_verified_summary_and_evidence():
    result = SpeakerAgent._compact_result(
        {
            "summary": "Le prototype demande une batterie de secours.",
            "results": [
                {
                    "title": "Notice",
                    "url": "https://example.org/notice",
                    "excerpt": "Alimentation de secours nécessaire.",
                }
            ],
        }
    )
    assert "batterie de secours" in result["summary"]
    assert result["sources"][0]["excerpt"] == "Alimentation de secours nécessaire."
    assert result["sources"][0]["url"] == "https://example.org/notice"


def test_canceled_voice_draft_is_not_presented_as_a_delivered_answer():
    from quorumy.workspace.core.models import Speech

    state = QuorumyState(
        project_id="quorumy",
        protocol_version=12,
        speeches=[
            Speech(text="Annulé", reason="direct_address", status="canceled"),
            Speech(text="Lu", reason="direct_address", status="finished"),
            Speech(text="Partiel", reason="direct_address", status="interrupted"),
        ],
    )
    context = SpeakerAgent._context(state, {})
    assert context["recent_speech"] == ["Lu"]
    assert context["interrupted_speech"] == ["Partiel"]
