import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from quorumy.providers import LiveBackend, ProviderError
from quorumy.settings import AppSettings
from quorumy.workspace.api import app as api_module

PAGE = """
<a class="result__a" href="https://example.org/paper">Source primaire</a>
<td class="result__snippet">Extrait vérifiable.</td>
"""


def test_web_search_returns_public_references():
    async def scenario():
        backend = LiveBackend(
            AppSettings(_env_file=None),
            httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, text=PAGE)
                )
            ),
        )
        finding = await backend.research("Recherche", "robotique", {}, "web")
        assert finding.sources[0].url == "https://example.org/paper"
        assert "Extrait" in finding.summary
        await backend.close()

    asyncio.run(scenario())


def test_provider_failure_is_redacted_and_never_replaced_by_demo_data():
    async def scenario():
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(401, text="leaked-secret")
            )
        )
        backend = LiveBackend(AppSettings(_env_file=None), client)
        with pytest.raises(ProviderError, match="HTTP 401") as error:
            await backend.research("Question", "projet", {}, "web")
        assert "leaked-secret" not in str(error.value)
        await backend.close()

    asyncio.run(scenario())


def test_weather_is_not_a_dedicated_tool():
    async def scenario():
        backend = LiveBackend(AppSettings(_env_file=None))
        with pytest.raises(ProviderError, match="Unknown research tool"):
            await backend.research("météo à Paris", "réunion", {}, "weather")
        await backend.close()

    asyncio.run(scenario())


def test_web_configuration_does_not_expose_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("QUORUMY_DATABASE_PATH", str(tmp_path / "api.sqlite3"))
    from quorumy.workspace.api import app as api_module

    monkeypatch.setattr(
        api_module,
        "AppSettings",
        lambda: AppSettings(_env_file=None, hf_token="private-token"),
    )
    with TestClient(api_module.create_app()) as client:
        response = client.get("/v1/bootstrap")
        assert response.status_code == 200
        assert "private-token" not in response.text
        assert client.get("/").status_code == 200
        assert client.get("/.env").status_code == 404
        assert client.get("/.Secrets").status_code == 404


def test_websocket_origin_validation_and_authenticated_unified_session(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("QUORUMY_DATABASE_PATH", str(tmp_path / "api.sqlite3"))
    with TestClient(api_module.create_app()) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/v1/live", headers={"origin": "https://untrusted.example"}
            ):
                pass
        with client.websocket_connect(
            "/v1/live", headers={"origin": "http://testserver"}
        ) as ws:
            ws.send_json(
                {
                    "type": "client.hello",
                    "protocol_version": 14,
                    "client_id": "test",
                    "access_token": "wrong",
                }
            )
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()
        token = client.get("/v1/bootstrap").json()["access_token"]
        with client.websocket_connect(
            "/v1/live", headers={"origin": "http://testserver"}
        ) as ws:
            ws.send_json(
                {
                    "type": "client.hello",
                    "protocol_version": 14,
                    "client_id": "test",
                    "access_token": token,
                }
            )
            assert ws.receive_json()["type"] == "backend.hello"
        assert client.get("/v1/sessions/unknown/export").status_code == 403
