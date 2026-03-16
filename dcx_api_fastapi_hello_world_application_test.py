"""
CONTEXT:
This file verifies the minimal FastAPI hello-world bootstrap for the DCX API workspace.
It sits next to the application file so the contract and its executable verification stay locally visible together.
"""

from fastapi.testclient import TestClient

from dcx_api_fastapi_hello_world_application import app

client = TestClient(app)


def test_root_route_returns_ok_wrapper() -> None:
    response = client.get("/")
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["message"] == "DCX API backend hello world"


def test_root_route_returns_backend_identity() -> None:
    response = client.get("/")
    payload = response.json()

    assert payload["data"]["service_name"] == "dcx_api"
    assert payload["data"]["status"] == "ready"


def test_root_route_is_side_effect_free() -> None:
    first = client.get("/").json()
    second = client.get("/").json()

    assert first == second
    assert first["context"]["side_effects_executed"] == []


def test_welcome_route_returns_ok_wrapper() -> None:
    response = client.get("/api/bootstrap/welcome")
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["message"] == "Welcome to the connected DCX MVP shell."
    assert "latest_raw_message" in payload["data"]


def test_welcome_route_allows_local_frontend_origin() -> None:
    response = client.get(
        "/api/bootstrap/welcome",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_welcome_route_returns_latest_raw_message_payload_shape() -> None:
    response = client.get("/api/bootstrap/welcome")
    latest_raw_message = response.json()["data"]["latest_raw_message"]

    assert latest_raw_message["status"] in {"ready", "empty"}
    assert "preview_text" in latest_raw_message
