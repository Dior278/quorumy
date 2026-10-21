from __future__ import annotations

import inspect
from typing import cast

from quorumy.workspace import config
from quorumy.workspace.core import coordinator, speaker


def test_prompt_catalog_formats_every_role() -> None:
    prompts = config.PROMPTS
    assert "Quorumy" in prompts.identity("Quorumy")
    assert "<SILENT>" in prompts.speaker_stream("Quorumy")
    assert "speak" in prompts.speaker_structured("Quorumy", '{"speak": true}')
    assert "source_ids" in prompts.notes("Quorumy")
    assert "title" in prompts.naming("Quorumy")
    assert "live board" in prompts.board("Quorumy")
    assert "source_card_ids" in prompts.board("Quorumy")
    assert "Card count is neutral" in prompts.board_review()
    assert "semantic equivalence" in prompts.board_review()
    assert "Omission never deletes" in prompts.board_review()
    assert "tool" in prompts.worker("Quorumy", '{"tool": null}')
    assert set(prompts.jev_questions("Quorumy")) == {
        "addressee",
        "route",
        "memory",
        "initiative",
        "speech_depth",
        "timing",
    }


def test_implementation_modules_reference_central_prompt_catalog() -> None:
    for module in (speaker, coordinator):
        source = inspect.getsource(module)
        assert "PROMPTS" in source
        assert "You are {" not in source
        assert "system_identity" not in source


def test_semantic_decision_contract_contains_no_behavioral_scores_or_thresholds() -> (
    None
):
    questions = config.PROMPTS.jev_questions("Quorumy")
    for question in questions.values():
        assert isinstance(question, dict)
        typed_question = cast(dict[str, object], question)
        assert typed_question.get("type") == "choice"
    source = inspect.getsource(config)
    assert not {
        "addressed_threshold",
        "mission_threshold",
        "memory_threshold",
    }.intersection(source.split())


def test_jev_contract_handles_asr_names_and_implicit_information_needs() -> None:
    questions = config.PROMPTS.jev_questions("Quorumy")
    addressee = str(questions["addressee"])
    route = str(questions["route"])
    initiative = str(questions["initiative"])
    assert "speech-recognition distortions" in addressee
    assert "exact spelling" in addressee
    assert "desire for information" in route
    assert "initiative=proactive" in route
    assert "without naming the AI directly" in initiative
