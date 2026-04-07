"""
CONTEXT:
This file verifies the token-gated public build-time API proof route.
It ensures the first Astro build-time fetch proof stays secure and returns the expected wrapper.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.public.dcx_api_routes_public_build_time_api_test as public_build_time_api_test_routes

client = TestClient(app)


def test_build_time_api_test_route_returns_payload_for_valid_token() -> None:
    with patch.object(
        public_build_time_api_test_routes,
        "read_dcx_public_build_time_api_test_payload_capability",
        return_value={
            "build_test_message": "build proof ok",
            "backend_runtime_environment": "production",
            "issued_at_ts_ms": 1775400000000,
        },
    ):
        response = client.get(
            "/public/build-time/api-test",
            headers={"X-DCX-Public-Build-Token": "top-secret-build-token"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload == {
        "ok": True,
        "data": {
            "build_test_message": "build proof ok",
            "backend_runtime_environment": "production",
            "issued_at_ts_ms": 1775400000000,
        },
        "context": {
            "what_happened": "The backend accepted one secure build-time proof read for the DCX public Astro build.",
            "side_effects_executed": [],
            "next_steps": [
                "Wire the real public UX-string bundle onto the same build-time fetch pattern.",
            ],
            "related_operations": [
                "read_dcx_public_build_time_api_test_payload_capability",
            ],
        },
    }


def test_build_time_api_test_route_rejects_missing_token() -> None:
    with patch.object(
        public_build_time_api_test_routes,
        "read_dcx_public_build_time_api_test_payload_capability",
        side_effect=RuntimeError("API_PUBLIC_BUILD_TOKEN_REQUIRED"),
    ):
        response = client.get("/public/build-time/api-test")
        payload = response.json()

    assert response.status_code == 401
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_PUBLIC_BUILD_TOKEN_REQUIRED",
            "message": "The public build token header is required.",
            "suggested_action": "Configure the Astro build to send X-DCX-Public-Build-Token and retry.",
        },
    }


def test_build_time_api_test_route_rejects_invalid_token() -> None:
    with patch.object(
        public_build_time_api_test_routes,
        "read_dcx_public_build_time_api_test_payload_capability",
        side_effect=RuntimeError("API_PUBLIC_BUILD_TOKEN_INVALID"),
    ):
        response = client.get(
            "/public/build-time/api-test",
            headers={"X-DCX-Public-Build-Token": "wrong-token"},
        )
        payload = response.json()

    assert response.status_code == 401
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_PUBLIC_BUILD_TOKEN_INVALID",
            "message": "The provided public build token is invalid.",
            "suggested_action": "Confirm the frontend and backend build tokens match exactly and retry.",
        },
    }
