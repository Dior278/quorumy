from fastapi.testclient import TestClient

from quorumy.workspace.api import app as api_module


def test_account_keeps_the_hugging_face_key_on_the_server(monkeypatch, tmp_path):
    monkeypatch.setenv("QUORUMY_DATABASE_PATH", str(tmp_path / "shared.sqlite3"))
    monkeypatch.setenv("QUORUMY_ACCOUNTS_PATH", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.setenv("QUORUMY_ACCOUNTS_DIR", str(tmp_path / "rooms"))
    monkeypatch.setenv("QUORUMY_AUTH", "required")
    with TestClient(api_module.create_app()) as client:
        created = client.post(
            "/v1/register",
            json={
                "name": "Pavel",
                "password": "reunion-secrete",
                "hf_token": "hf_private_token",
                "model": "Qwen/Qwen2.5-7B-Instruct:cheapest",
            },
        )
        assert created.status_code == 200
        assert "hf_private_token" not in created.text
        bootstrap = client.get("/v1/bootstrap")
        assert bootstrap.status_code == 200
        payload = bootstrap.json()
        assert payload["account_name"] == "Pavel"
        assert payload["hf_ready"] is True
        assert "hf_private_token" not in bootstrap.text
        assert payload["active_model"].startswith("huggingface/")
