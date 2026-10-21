"""Speech synthesis through Kokoro on the Hugging Face router."""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator

import httpx

from quorumy.workspace.config import TTSModelConfig
from quorumy.workspace.core.models import AudioResult
from quorumy.workspace.core.ports import AudioChunkCallback, TextTimingCallback

# Kokoro has no German voice: a German meeting uses af_heart.
_VOICES = {
    "fr": "ff_siwis",
    "en": "af_heart",
    "es": "ef_dora",
    "pt": "pf_dora",
    "de": "af_heart",
}


class HuggingFaceTTS:
    def __init__(
        self,
        config: TTSModelConfig,
        api_key: str | None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self.api_key = (api_key or "").strip()
        self._client = client or httpx.AsyncClient(timeout=45)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def voice_for(self, language: str) -> str:
        return _VOICES.get(language, self.config.voice_id)

    async def synthesize(
        self,
        text: str,
        language: str,
        padding_bonus: float | None = None,
        temp: float | None = None,
    ) -> AudioResult:
        del padding_bonus, temp
        audio = await self._speak(text, language)
        return AudioResult(
            data_base64=base64.b64encode(audio).decode(),
            format="wav",
            sample_rate=24000,
        )

    async def stream(
        self,
        text: str,
        language: str,
        on_chunk: AudioChunkCallback,
        on_text: TextTimingCallback | None = None,
    ) -> None:
        async def once() -> AsyncIterator[str]:
            yield text

        await self.stream_chunks(once(), language, on_chunk, on_text)

    async def stream_chunks(
        self,
        text_chunks: AsyncIterator[str],
        language: str,
        on_chunk: AudioChunkCallback,
        on_text: TextTimingCallback | None = None,
    ) -> None:
        async for text in text_chunks:
            cleaned = " ".join(text.split()).strip()
            if not cleaned:
                continue
            audio = await self._speak(cleaned, language)
            if on_text is not None:
                await on_text(cleaned, 0, 0)
            await on_chunk(audio, 24000, "wav")

    async def _speak(self, text: str, language: str) -> bytes:
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            raise RuntimeError("Nothing to speak.")
        if not self.api_key:
            raise RuntimeError("Hugging Face voice is unavailable.")
        try:
            response = await self._client.post(
                self.config.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.config.model,
                    "input": cleaned[:4000],
                    "voice": self.voice_for(language),
                    "response_format": "wav",
                },
            )
        except httpx.HTTPError as error:
            raise RuntimeError("Hugging Face voice is unavailable.") from error
        content_type = response.headers.get("content-type", "")
        if response.is_error or "json" in content_type or response.content[:1] == b"{":
            raise RuntimeError(
                f"Hugging Face voice is unavailable (HTTP {response.status_code})."
            )
        if not response.content:
            raise RuntimeError("Hugging Face voice returned empty audio.")
        return response.content
