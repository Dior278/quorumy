from __future__ import annotations

import json

from quorumy.workspace.config import AppConfig, default_config_text, load_config


def test_default_models_are_hugging_face() -> None:
    config = AppConfig.model_validate(json.loads(default_config_text()))
    assert config.llm.roles.speaker.startswith("huggingface/")
    assert {(item.provider, item.transport) for item in config.llm.models} == {
        ("huggingface", "chat_completions")
    }
    assert config.voice.stt.active == "huggingface/openai/whisper-large-v3"
    assert config.voice.tts.active == "huggingface/hexgrad/Kokoro-82M"


def test_old_config_file_stays_intact_and_runtime_uses_hugging_face(tmp_path):
    raw = {
        "server": {"host": "127.0.0.1", "port": 9000},
        "voice": {"stt": {"provider": "gradium", "model": "default"}},
        "llm": {"active_model": "gpt"},
        "tools": {"exa": {"secret_env": "EXA_API_KEY"}},
    }
    path = tmp_path / "config.json"
    original = json.dumps(raw)
    path.write_text(original, encoding="utf-8")
    config = load_config(path)
    assert config.server.port == 9000
    assert config.voice.stt.active.startswith("huggingface/")
    assert config.llm.roles.worker.startswith("huggingface/")
    assert path.read_text(encoding="utf-8") == original
