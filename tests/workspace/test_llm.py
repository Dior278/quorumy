from __future__ import annotations

import json

import httpx
import pytest

from quorumy.workspace.config import AppConfig, default_config_text
from quorumy.workspace.llm import ChatGenerator


@pytest.mark.asyncio
async def test_chat_uses_the_configured_hugging_face_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HF_TOKEN", "test")
    config = AppConfig.model_validate(json.loads(default_config_text()))
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "hello"}}]}
        )

    transport = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = ChatGenerator(config.llm, transport)
    result = await client.generate(
        [{"role": "user", "content": "hi"}], config.llm.roles.worker
    )
    assert captured["model"] == "Qwen/Qwen2.5-7B-Instruct:cheapest"
    assert captured["max_tokens"] == 4096
    assert "messages" in captured and result.content == "hello"
    await transport.aclose()
