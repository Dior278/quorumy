from pathlib import Path

from quorumy.settings import AppSettings


def test_secrets_file_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    env = tmp_path / ".env"
    secrets = tmp_path / ".Secrets"
    env.write_text('HF_TOKEN="old-local-test"\n', encoding="utf-8")
    secrets.write_text('HF_TOKEN="new-local-test"\n', encoding="utf-8")
    settings = AppSettings(_env_file=(env, secrets))
    assert settings.key("hf_token") == "new-local-test"
    assert "new-local-test" not in repr(settings)


def test_published_environment_example_is_loadable():
    example = Path(__file__).resolve().parents[1] / ".env.example"
    settings = AppSettings(_env_file=example)
    assert settings.key("hf_token") == ""
    assert "Qwen" in settings.hf_model
