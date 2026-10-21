"""Replacing a stale connection must preserve exclusive, paused session control."""

from fastapi.testclient import TestClient

from quorumy.workspace.api import app as api


def receive_until(ws, predicate):
    for _ in range(30):
        event = ws.receive_json()
        if predicate(event):
            return event
    raise AssertionError("Expected protocol event was not received")


def test_same_tab_can_replace_stale_socket_but_another_tab_cannot(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("QUORUMY_DATABASE_PATH", str(tmp_path / "reconnect.sqlite3"))
    with TestClient(api.create_app()) as client:
        token = client.get("/v1/bootstrap").json()["access_token"]
        hello = {
            "type": "client.hello",
            "protocol_version": 14,
            "client_id": "same-tab",
            "access_token": token,
        }
        with client.websocket_connect(
            "/v1/live", headers={"origin": "http://testserver"}
        ) as old:
            old.send_json(hello)
            receive_until(old, lambda e: e["type"] == "state.snapshot")
            old.send_json(
                {"type": "session.start", "capture_mode": "text", "consent": True}
            )
            active = receive_until(
                old,
                lambda e: (
                    e["type"] == "state.snapshot"
                    and e["state"]["session_status"] == "listening"
                ),
            )
            with client.websocket_connect(
                "/v1/live", headers={"origin": "http://testserver"}
            ) as new:
                new.send_json(hello)
                paused = receive_until(new, lambda e: e["type"] == "state.snapshot")
                assert paused["state"]["session_status"] == "paused"
                assert paused["state"]["consent_at"] is None
                assert paused["state"]["session_id"] == active["state"]["session_id"]
                with client.websocket_connect(
                    "/v1/live", headers={"origin": "http://testserver"}
                ) as other:
                    other.send_json({**hello, "client_id": "other-tab"})
                    assert other.receive_json()["code"] == "CONNECTION_REJECTED"
                # Closing/rejecting older or other sockets cannot pause this owner.
                new.send_json(
                    {"type": "session.command", "command": "resume", "consent": True}
                )
                receive_until(
                    new,
                    lambda e: (
                        e["type"] == "state.snapshot"
                        and e["state"]["session_status"] == "listening"
                    ),
                )
                new.send_json({"type": "voice.mode", "mode": "muted"})
                current = receive_until(
                    new,
                    lambda e: (
                        e["type"] == "state.snapshot"
                        and e["state"]["voice_mode"] == "muted"
                    ),
                )
                assert current["state"]["session_status"] == "listening"
