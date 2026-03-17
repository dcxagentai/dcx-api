"""
CONTEXT:
This file verifies the minimal FastAPI hello-world bootstrap for the DCX API workspace.
It sits next to the application file so the contract and its executable verification stay locally visible together.
"""

from fastapi.testclient import TestClient

from dcx_api_app import app

client = TestClient(app)


def test_root_route_returns_ok_wrapper() -> None:
    response = client.get("/")
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["message"] == "Welcome to the connected DCX MVP shell."


def test_root_route_returns_backend_identity() -> None:
    response = client.get("/")
    payload = response.json()

    assert payload["data"]["service_name"] == "dcx_api"
    assert payload["data"]["status"] == "ready"


def test_root_route_is_side_effect_free() -> None:
    payload = client.get("/").json()

    assert payload["context"]["side_effects_executed"] == []
    assert payload["data"]["latest_raw_message"]["status"] in {"ready", "empty"}


def test_root_route_allows_local_frontend_origin() -> None:
    response = client.get(
        "/",
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_root_route_allows_cloudflare_pages_frontend_origin() -> None:
    response = client.get(
        "/",
        headers={"Origin": "https://dcx-admin.pages.dev"},
    )

    assert response.headers["access-control-allow-origin"] == "https://dcx-admin.pages.dev"


def test_root_route_returns_latest_raw_message_payload_shape() -> None:
    response = client.get("/")
    latest_raw_message = response.json()["data"]["latest_raw_message"]

    assert latest_raw_message["status"] in {"ready", "empty"}
    assert "preview_text" in latest_raw_message
