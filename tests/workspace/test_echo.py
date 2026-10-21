from datetime import UTC, datetime, timedelta

import pytest

from quorumy.workspace.core.models import Speech
from quorumy.workspace.echo import remove_playback_echo

NOW = datetime(2026, 1, 1, tzinfo=UTC)
REPLY = (
    "Le prototype du robot peut être présenté vendredi avec une batterie de secours."
)


def played(**overrides):
    fields = dict(
        text=REPLY,
        reason="direct_address",
        status="finished",
        playback_started_at=(NOW - timedelta(seconds=8)).isoformat(),
        playback_ended_at=(NOW - timedelta(seconds=1)).isoformat(),
    )
    fields.update(overrides)
    return Speech(**fields)


def test_recent_playback_is_not_a_new_human_turn():
    assert (
        remove_playback_echo(REPLY.upper().replace("Ê", "E"), [played()], now=NOW) == ""
    )


def test_correction_after_echo_is_preserved():
    correction = "Non, le prototype doit être présenté lundi."
    assert (
        remove_playback_echo(REPLY + " " + correction, [played()], now=NOW)
        == correction
    )


def test_human_speech_before_echo_is_preserved():
    correction = "Attends, je souhaite corriger la date."
    assert (
        remove_playback_echo(correction + " " + REPLY, [played()], now=NOW)
        == correction
    )


@pytest.mark.parametrize(
    "text",
    [
        REPLY.replace("vendredi", "lundi"),
        REPLY.replace("peut être", "ne peut pas être"),
        "Je cite : « " + REPLY + " »",
        "Le budget est maintenant de 200 euros au lieu de 100 euros.",
        "Oui, je suis d’accord.",
    ],
)
def test_novel_words_numbers_negation_and_quotations_survive(text):
    assert remove_playback_echo(text, [played()], now=NOW) == text


def test_old_or_unplayed_response_is_never_filtered():
    old = played(playback_ended_at=(NOW - timedelta(seconds=30)).isoformat())
    assert remove_playback_echo(REPLY, [old], now=NOW) == REPLY
    canceled = played(
        status="canceled", playback_started_at=None, playback_ended_at=None
    )
    assert remove_playback_echo(REPLY, [canceled], now=NOW) == REPLY
