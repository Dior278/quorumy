from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".Secrets"), env_file_encoding="utf-8-sig", extra="ignore"
    )

    hf_token: SecretStr = SecretStr("")
    hf_model: str = "Qwen/Qwen2.5-7B-Instruct:cheapest"

    def key(self, name: str) -> str:
        value = getattr(self, name)
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        raw = raw.strip()
        if not raw or raw.lower().startswith(
            ("ta_cle", "ton_workspace", "your_", "replace_")
        ):
            return ""
        return raw
