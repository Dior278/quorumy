from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from quorumy.workspace.adapters.stt_registry import STTRegistry
from quorumy.workspace.adapters.tts_registry import TTSRegistry
from quorumy.workspace.config import STTRegistryConfig, TTSRegistryConfig
from quorumy.workspace.core.models import AudioResult
from quorumy.workspace.core.ports import (
    AudioChunkCallback,
    EventCallback,
    TextCallback,
    TextTimingCallback,
)


class FakeSTT:
    rotate_after_seconds = 300.0

    def __init__(self, *, fails: bool = False) -> None:
        self.available = True
        self.connected = False
        self.fails = fails
        self.sent: list[bytes] = []

    async def start(
        self,
        on_partial: TextCallback,
        on_final: TextCallback,
        on_event: EventCallback,
        language: str,
    ) -> None:
        del on_partial, on_final, on_event, language
        if self.fails:
            raise RuntimeError("provider unavailable")
        self.connected = True

    async def send(self, audio: bytes) -> None:
        self.sent.append(audio)

    async def flush(self) -> None:
        return None

    async def stop(self) -> None:
        self.connected = False


class FakeTTS:
    available = True

    def __init__(
        self, *, fails: bool = False, emits_before_failure: bool = False
    ) -> None:
        self.fails = fails
        self.emits_before_failure = emits_before_failure
        self.received: list[str] = []

    async def synthesize(
        self,
        text: str,
        language: str,
        padding_bonus: float | None = None,
        temp: float | None = None,
    ) -> AudioResult:
        del text, language, padding_bonus, temp
        if self.fails:
            raise RuntimeError("provider unavailable")
        return AudioResult(data_base64="AA==", format="pcm_24000", sample_rate=24000)

    async def stream(
        self,
        text: str,
        language: str,
        on_chunk: AudioChunkCallback,
        on_text: TextTimingCallback | None = None,
    ) -> None:
        async def chunks() -> AsyncIterator[str]:
            yield text

        await self.stream_chunks(chunks(), language, on_chunk, on_text)

    async def stream_chunks(
        self,
        text_chunks: AsyncIterator[str],
        language: str,
        on_chunk: AudioChunkCallback,
        on_text: TextTimingCallback | None = None,
    ) -> None:
        del language, on_text
        async for text in text_chunks:
            self.received.append(text)
        if self.emits_before_failure:
            await on_chunk(b"audio", 24000, "pcm_24000")
        if self.fails:
            raise RuntimeError("provider unavailable")
        await on_chunk(b"audio", 24000, "pcm_24000")


def stt_config() -> STTRegistryConfig:
    return STTRegistryConfig.model_validate(
        {
            "active": "huggingface/primary",
            "providers": [
                {
                    "id": "huggingface/primary",
                    "endpoint": "https://huggingface.test/primary",
                    "secret_env": "HF_TOKEN",
                },
                {
                    "id": "huggingface/fallback",
                    "endpoint": "https://huggingface.test/fallback",
                    "secret_env": "HF_TOKEN",
                },
            ],
        }
    )


def tts_config() -> TTSRegistryConfig:
    return TTSRegistryConfig.model_validate(
        {
            "active": "huggingface/primary",
            "providers": [
                {
                    "id": "huggingface/primary",
                    "endpoint": "browser://primary",
                    "secret_env": "HF_TOKEN",
                },
                {
                    "id": "huggingface/fallback",
                    "endpoint": "browser://fallback",
                    "secret_env": "HF_TOKEN",
                },
            ],
        }
    )


@pytest.mark.asyncio
async def test_stt_registry_falls_back_to_next_registered_provider() -> None:
    primary = FakeSTT(fails=True)
    fallback = FakeSTT()
    registry = STTRegistry(
        stt_config(), {"huggingface/primary": primary, "huggingface/fallback": fallback}
    )
    events: list[tuple[str, dict[str, object]]] = []

    async def text(_: str) -> None:
        return None

    async def event(kind: str, detail: dict[str, object]) -> None:
        events.append((kind, detail))

    await registry.start(text, text, event, "en")
    await registry.send(b"pcm")

    assert fallback.connected
    assert fallback.sent == [b"pcm"]
    assert events[-1] == ("provider.selected", {"provider": "huggingface/fallback"})


@pytest.mark.asyncio
async def test_tts_registry_replays_text_only_before_audio_started() -> None:
    primary = FakeTTS(fails=True)
    fallback = FakeTTS()
    registry = TTSRegistry(
        tts_config(), {"huggingface/primary": primary, "huggingface/fallback": fallback}
    )
    audio: list[bytes] = []

    async def chunks() -> AsyncIterator[str]:
        yield "First sentence."
        yield "Second sentence."

    async def collect(data: bytes, *_args: Any) -> None:
        audio.append(data)

    await registry.stream_chunks(chunks(), "en", collect)

    assert primary.received == ["First sentence.", "Second sentence."]
    assert fallback.received == ["First sentence.", "Second sentence."]
    assert audio == [b"audio"]


@pytest.mark.asyncio
async def test_tts_registry_never_duplicates_after_audio_started() -> None:
    primary = FakeTTS(fails=True, emits_before_failure=True)
    fallback = FakeTTS()
    registry = TTSRegistry(
        tts_config(), {"huggingface/primary": primary, "huggingface/fallback": fallback}
    )

    async def chunks() -> AsyncIterator[str]:
        yield "One sentence."

    async def collect(*_args: Any) -> None:
        return None

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await registry.stream_chunks(chunks(), "en", collect)

    assert fallback.received == []


async def test_stt_send_failure_selects_another_provider_before_retrying_failed_one():
    class BrokenSend(FakeSTT):
        async def send(self, audio):
            raise RuntimeError("transport failed")

    primary, fallback = BrokenSend(), FakeSTT()
    registry = STTRegistry(
        stt_config(), {"huggingface/primary": primary, "huggingface/fallback": fallback}
    )

    async def callback(*args):
        pass

    await registry.start(callback, callback, callback, "fr")
    await registry.send(b"frame")
    assert fallback.sent == [b"frame"]
    assert not primary.connected
    await registry.stop()


async def test_multiple_tts_failures_preserve_text_for_last_provider():
    config = tts_config()
    config.providers.append(
        config.providers[0].model_copy(update={"id": "huggingface/last"})
    )
    first, second, last = FakeTTS(fails=True), FakeTTS(fails=True), FakeTTS()
    registry = TTSRegistry(
        config,
        {
            "huggingface/primary": first,
            "huggingface/fallback": second,
            "huggingface/last": last,
        },
    )

    async def chunks():
        yield "Le robot est prêt."
        yield "La démonstration peut commencer."

    async def collect(*args):
        pass

    await registry.stream_chunks(chunks(), "fr", collect)
    assert last.received == first.received == second.received
    assert len(last.received) == 2
