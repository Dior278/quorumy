"""Buffered speech recognition through a Hugging Face Inference endpoint."""

from __future__ import annotations

import asyncio
import logging
import struct

import httpx

from quorumy.workspace.config import STTModelConfig
from quorumy.workspace.core.ports import EventCallback, TextCallback

logger = logging.getLogger("uvicorn.error").getChild("huggingface-stt")


def pcm16_wav(pcm: bytes, sample_rate: int) -> bytes:
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        len(pcm),
    )
    return header + pcm


class HuggingFaceSTT:
    def __init__(self, config: STTModelConfig, api_key: str | None) -> None:
        self.config = config
        self.api_key = (api_key or "").strip()
        self._buffer = bytearray()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._on_final: TextCallback | None = None
        self._stopped = asyncio.Event()
        self._connected = False
        self._client = httpx.AsyncClient(timeout=45)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def rotate_after_seconds(self) -> float:
        return self.config.rotate_after_seconds

    async def start(
        self,
        on_partial: TextCallback,
        on_final: TextCallback,
        on_event: EventCallback,
        language: str,
    ) -> None:
        del on_partial, language
        await self.stop()
        self._on_final = on_final
        self._stopped = asyncio.Event()
        self._connected = True
        self._task = asyncio.create_task(self._pump())
        await on_event("provider.selected", {"provider": self.config.id})

    async def send(self, audio: bytes) -> None:
        if not self._connected or not audio:
            return
        async with self._lock:
            self._buffer.extend(audio)
            max_bytes = 24000 * 2 * 30
            if len(self._buffer) > max_bytes:
                del self._buffer[: len(self._buffer) - max_bytes]

    async def flush(self) -> None:
        await self._transcribe()

    async def stop(self) -> None:
        self._connected = False
        self._stopped.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        async with self._lock:
            self._buffer.clear()

    async def aclose(self) -> None:
        await self.stop()
        await self._client.aclose()

    async def _pump(self) -> None:
        while not self._stopped.is_set():
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=6)
                return
            except TimeoutError:
                await self._transcribe()

    async def _transcribe(self) -> None:
        async with self._lock:
            if len(self._buffer) < 24000 * 2:
                return
            pcm = bytes(self._buffer)
            self._buffer.clear()
        try:
            response = await self._client.post(
                self.config.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "audio/wav",
                },
                content=pcm16_wav(pcm, 24000),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            logger.warning("whisper.failed", exc_info=True)
            return
        text = payload.get("text") if isinstance(payload, dict) else ""
        cleaned = " ".join(str(text).split()).strip()
        if cleaned and self._on_final is not None:
            await self._on_final(cleaned)
