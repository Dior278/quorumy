from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, model_validator

from quorumy.workspace.languages import QuorumyLanguage
from quorumy.workspace.prompts import PROMPTS as PROMPTS

PROJECT_ROOT = Path(__file__).resolve().parents[3]
USER_CONFIG = PROJECT_ROOT / ".data" / "config.json"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductConfig(StrictModel):
    project_id: str
    display_name: str
    companion_name: str
    protocol_version: int


class ServerConfig(StrictModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)


class SessionConfig(StrictModel):
    language: QuorumyLanguage = "en"
    notes_interval_seconds: float = Field(default=20, gt=0)


class PolicyConfig(StrictModel):
    stable_floor_gap_seconds: float = Field(default=1.5, ge=0)
    direct_floor_gap_seconds: float = Field(default=0.8, ge=0)
    awaited_floor_gap_seconds: float = Field(default=3.0, ge=0)
    unsolicited_speech_cooldown_seconds: float = Field(default=90, ge=0)
    research_max_concurrency: int = Field(default=3, ge=1, le=16)
    max_tool_steps: int = Field(default=4, ge=1, le=16)
    mission_timeout_seconds: float = Field(default=120, ge=1, le=600)


class StorageConfig(StrictModel):
    database_path: str = ""

    def resolved_path(self) -> Path:
        if self.database_path:
            return Path(self.database_path).expanduser()
        return Path(
            os.environ.get(
                "QUORUMY_DATABASE_PATH", PROJECT_ROOT / ".data" / "quorumy.sqlite3"
            )
        )


class STTModelConfig(StrictModel):
    id: str
    provider: Literal["huggingface"] | None = None
    endpoint: str
    secret_env: str
    model: str | None = None
    input_format: str = "pcm_24000"
    language: str = "en"
    rotate_after_seconds: float = Field(default=285, gt=0, le=3600)

    @model_validator(mode="after")
    def resolve_reference(self) -> STTModelConfig:
        try:
            inferred_provider, inferred_model = self.id.split("/", 1)
        except ValueError as error:
            raise ValueError("STT model IDs must use provider/model") from error
        if inferred_provider not in {"huggingface"}:
            raise ValueError(f"unsupported STT provider: {inferred_provider}")
        if self.provider is not None and self.provider != inferred_provider:
            raise ValueError("STT provider conflicts with its provider/model ID")
        if self.model is not None and self.model != inferred_model:
            raise ValueError("STT model conflicts with its provider/model ID")
        object.__setattr__(self, "provider", inferred_provider)
        object.__setattr__(self, "model", inferred_model)
        return self


class STTRegistryConfig(StrictModel):
    active: str
    providers: list[STTModelConfig]

    @model_validator(mode="after")
    def validate_registry(self) -> STTRegistryConfig:
        ids = [item.id for item in self.providers]
        if len(ids) != len(set(ids)):
            raise ValueError("STT model IDs must be unique")
        if self.active not in ids:
            raise ValueError("voice.stt.active must reference a registered STT model")
        return self

    def ordered(self) -> list[STTModelConfig]:
        active = next(item for item in self.providers if item.id == self.active)
        return [active, *(item for item in self.providers if item.id != self.active)]


class TTSModelConfig(StrictModel):
    id: str
    provider: Literal["huggingface"] | None = None
    endpoint: str
    secret_env: str
    voice_id: str = "ff_siwis"
    model: str | None = None
    output_format: str = "wav"

    @model_validator(mode="after")
    def resolve_reference(self) -> TTSModelConfig:
        try:
            inferred_provider, inferred_model = self.id.split("/", 1)
        except ValueError as error:
            raise ValueError("TTS model IDs must use provider/model") from error
        if inferred_provider not in {"huggingface"}:
            raise ValueError(f"unsupported TTS provider: {inferred_provider}")
        if self.provider is not None and self.provider != inferred_provider:
            raise ValueError("TTS provider conflicts with its provider/model ID")
        if self.model is not None and self.model != inferred_model:
            raise ValueError("TTS model conflicts with its provider/model ID")
        object.__setattr__(self, "provider", inferred_provider)
        object.__setattr__(self, "model", inferred_model)
        return self


class TTSRegistryConfig(StrictModel):
    active: str
    providers: list[TTSModelConfig]

    @model_validator(mode="after")
    def validate_registry(self) -> TTSRegistryConfig:
        ids = [item.id for item in self.providers]
        if len(ids) != len(set(ids)):
            raise ValueError("TTS model IDs must be unique")
        if self.active not in ids:
            raise ValueError("voice.tts.active must reference a registered TTS model")
        return self

    def ordered(self) -> list[TTSModelConfig]:
        active = next(item for item in self.providers if item.id == self.active)
        return [active, *(item for item in self.providers if item.id != self.active)]


class VoiceConfig(StrictModel):
    stt: STTRegistryConfig
    tts: TTSRegistryConfig

    @model_validator(mode="before")
    @classmethod
    def migrate_single_provider(cls, value):
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        for kind in ("stt", "tts"):
            old = migrated.get(kind)
            if isinstance(old, dict) and "providers" not in old and "provider" in old:
                provider = dict(old)
                provider["id"] = f"{provider['provider']}/{provider['model']}"
                migrated[kind] = {"active": provider["id"], "providers": [provider]}
        return migrated


class LLMModelConfig(StrictModel):
    id: str
    provider: Literal["huggingface"] | None = None
    model: str | None = None
    endpoint: str
    transport: Literal["responses", "chat_completions"]
    secret_env: str
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high"] | None = None
    max_output_tokens: int = Field(ge=1, le=8192)
    max_concurrency: int = Field(default=2, ge=1, le=16)
    timeout_seconds: float | None = Field(default=None, gt=0)
    input_usd_per_million_tokens: float = Field(ge=0)
    output_usd_per_million_tokens: float = Field(ge=0)

    @model_validator(mode="after")
    def resolve_reference(self) -> LLMModelConfig:
        try:
            inferred_provider, inferred_model = self.id.split("/", 1)
        except ValueError as error:
            raise ValueError("LLM model IDs must use provider/model") from error
        if inferred_provider not in {"huggingface"}:
            raise ValueError(f"unsupported LLM provider: {inferred_provider}")
        if self.provider is not None and self.provider != inferred_provider:
            raise ValueError("LLM provider conflicts with its provider/model ID")
        if self.model is not None and self.model != inferred_model:
            raise ValueError("LLM model conflicts with its provider/model ID")
        object.__setattr__(self, "provider", inferred_provider)
        object.__setattr__(self, "model", inferred_model)
        return self


class LLMRolesConfig(StrictModel):
    speaker: str
    worker: str
    notes: str
    board: str
    naming: str
    fallback: str


class LLMConfig(StrictModel):
    roles: LLMRolesConfig
    timeout_seconds: float = Field(default=30, gt=0)
    max_request_cost_usd: float = Field(default=6, ge=0)
    models: list[LLMModelConfig]

    @model_validator(mode="after")
    def validate_registry(self) -> LLMConfig:
        ids = [item.id for item in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("LLM model IDs must be unique")
        for role, model_id in self.roles.model_dump().items():
            if model_id not in ids:
                raise ValueError(f"llm.roles.{role} must reference a registered model")
        return self

    @property
    def active_model(self) -> str:
        return self.roles.speaker

    def select(self, model_id: str | None = None) -> LLMModelConfig:
        selected = model_id or self.roles.worker
        return next(item for item in self.models if item.id == selected)


class AppConfig(StrictModel):
    server: ServerConfig
    session: SessionConfig
    policy: PolicyConfig
    storage: StorageConfig
    voice: VoiceConfig
    llm: LLMConfig


def default_config_text() -> str:
    return (
        files("quorumy.workspace")
        .joinpath("default_config.json")
        .read_text(encoding="utf-8")
    )


def load_product() -> ProductConfig:
    path = Path(os.environ.get("QUORUMY_PRODUCT_FILE", PROJECT_ROOT / "product.json"))
    return ProductConfig.model_validate_json(path.read_text(encoding="utf-8"))


def _apply_hf_model(values: dict, model_name: str) -> None:
    model_name = model_name.strip() or "Qwen/Qwen2.5-7B-Instruct:cheapest"
    model_id = f"huggingface/{model_name}"
    if not any(item["id"] == model_id for item in values["llm"]["models"]):
        values["llm"]["models"] = [
            {
                "id": model_id,
                "endpoint": "https://router.huggingface.co/v1/chat/completions",
                "transport": "chat_completions",
                "secret_env": "HF_TOKEN",
                "max_output_tokens": 4096,
                "max_concurrency": 4,
                "input_usd_per_million_tokens": 0.2,
                "output_usd_per_million_tokens": 0.6,
            }
        ]
    values["llm"]["roles"] = {role: model_id for role in LLMRolesConfig.model_fields}


def load_config(path: Path | None = None) -> AppConfig:
    from quorumy.settings import AppSettings

    selected = path or Path(
        os.environ.get(
            "QUORUMY_CONFIG", os.environ.get("QUORUMY_CONFIG_FILE", USER_CONFIG)
        )
    )
    values = json.loads(default_config_text())
    if selected.exists():
        stored = json.loads(selected.read_text(encoding="utf-8"))
        for section, model in (
            ("server", ServerConfig),
            ("session", SessionConfig),
            ("policy", PolicyConfig),
            ("storage", StorageConfig),
        ):
            raw = stored.get(section)
            if isinstance(raw, dict):
                values[section].update(
                    {key: raw[key] for key in raw if key in model.model_fields}
                )
    else:
        settings = AppSettings()
        values["server"]["port"] = 8765
        values["session"]["language"] = "fr"
        _apply_hf_model(values, settings.hf_model)
        for provider in values["voice"]["stt"]["providers"]:
            provider["language"] = values["session"]["language"]
    return AppConfig.model_validate(values)


def secret(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        local = {}
        for path in (PROJECT_ROOT / ".env", PROJECT_ROOT / ".Secrets"):
            if path.is_file():
                local.update(dotenv_values(path, encoding="utf-8-sig"))
        value = local.get(name)
    return value.strip() if value and value.strip() else None


def account_config(base: AppConfig, *, model: str, database_path: Path) -> AppConfig:
    """One Hugging Face model and one database for a signed-in person."""
    values = base.model_dump()
    model_id = f"huggingface/{model}"
    models = values["llm"]["models"]
    if not any(item["id"] == model_id for item in models):
        models.append(
            {
                "id": model_id,
                "endpoint": "https://router.huggingface.co/v1/chat/completions",
                "transport": "chat_completions",
                "secret_env": "HF_TOKEN",
                "max_output_tokens": 4096,
                "max_concurrency": 4,
                "input_usd_per_million_tokens": 0.2,
                "output_usd_per_million_tokens": 0.6,
            }
        )
    values["llm"]["roles"] = {role: model_id for role in LLMRolesConfig.model_fields}
    stt_id = "huggingface/openai/whisper-large-v3"
    providers = values["voice"]["stt"]["providers"]
    if not any(item["id"] == stt_id for item in providers):
        providers.insert(
            0,
            {
                "id": stt_id,
                "endpoint": "https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3",
                "secret_env": "HF_TOKEN",
                "input_format": "pcm_24000",
                "language": values["session"]["language"],
            },
        )
    values["voice"]["stt"]["active"] = stt_id
    values["storage"]["database_path"] = str(database_path)
    return AppConfig.model_validate(values)
