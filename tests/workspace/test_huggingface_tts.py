from __future__ import annotations

import json

import httpx
import pytest

from quorumy.workspace.adapters.huggingface_tts import HuggingFaceTTS
from quorumy.workspace.config import AppConfig, default_config_text


def _voice() -> HuggingFaceTTS:
    config = AppConfig.model_validate(json.loads(default_config_text()))
    return HuggingFaceTTS(
        config.voice.tts.providers[0],
        "test-token",
        httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: _respond(request))
        ),
    )


_captured: dict[str, object] = {}


def _respond(request: httpx.Request) -> httpx.Response:
    _captured.clear()
    _captured.update(json.loads(request.content))
    _captured["authorization"] = request.headers["authorization"]
    _captured["url"] = str(request.url)
    return httpx.Response(
        200, content=b"RIFFfake", headers={"content-type": "audio/wav"}
    )


@pytest.mark.asyncio
async def test_kokoro_uses_the_french_voice_by_default() -> None:
    voice = _voice()
    result = await voice.synthesize("Bonjour.", "fr")
    assert _captured["model"] == "hexgrad/Kokoro-82M"
    assert _captured["voice"] == "ff_siwis"
    assert _captured["input"] == "Bonjour."
    assert _captured["response_format"] == "wav"
    assert str(_captured["url"]).endswith("/deepinfra/v1/openai/audio/speech")
    assert _captured["authorization"] == "Bearer test-token"
    assert result.format == "wav" and result.sample_rate == 24000
    await voice._client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "voice_id"),
    [("en", "af_heart"), ("es", "ef_dora"), ("pt", "pf_dora"), ("de", "af_heart")],
)
async def test_kokoro_voice_follows_the_meeting_language(language, voice_id) -> None:
    voice = _voice()
    chunks: list[tuple[bytes, str]] = []

    async def on_chunk(data: bytes, _rate: int, audio_format: str) -> None:
        chunks.append((data, audio_format))

    await voice.stream("Une phrase.", language, on_chunk)
    assert _captured["voice"] == voice_id
    assert chunks == [(b"RIFFfake", "wav")]
    await voice._client.aclose()


@pytest.mark.asyncio
async def test_voice_failure_does_not_repeat_the_provider_body() -> None:
    config = AppConfig.model_validate(json.loads(default_config_text()))

    def fail(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="leaked-secret")

    voice = HuggingFaceTTS(
        config.voice.tts.providers[0],
        "test-token",
        httpx.AsyncClient(transport=httpx.MockTransport(fail)),
    )
    with pytest.raises(RuntimeError, match="HTTP 401") as error:
        await voice.synthesize("Bonjour.", "fr")
    assert "leaked-secret" not in str(error.value)
    await voice._client.aclose()
