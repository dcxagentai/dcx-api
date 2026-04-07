"""
CONTEXT:
This file verifies the token-gated build-time live public UX-string bundle route.
It keeps the real public-content Astro build path executable before the old generated snapshot is retired.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.public.dcx_api_routes_public_build_time_ux_strings_bundle as public_bundle_routes

client = TestClient(app)


def test_build_time_ux_strings_bundle_route_returns_payload_for_valid_token() -> None:
    with patch.object(
        public_bundle_routes,
        "read_dcx_public_build_time_ux_strings_bundle_capability",
        return_value={
            "en": {"home": {"meta_title": "DCX | Public queue"}},
            "es": {"home": {"meta_title": "DCX | Cola publica"}},
            "fr": {"home": {"meta_title": "DCX | File publique"}},
            "de": {"home": {"meta_title": "DCX | Offentliche Warteliste"}},
        },
    ):
        response = client.get(
            "/public/build-time/ux-strings-bundle",
            headers={"X-DCX-Public-Build-Token": "top-secret-build-token"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload == {
        "ok": True,
        "data": {
            "bundle": {
                "en": {"home": {"meta_title": "DCX | Public queue"}},
                "es": {"home": {"meta_title": "DCX | Cola publica"}},
                "fr": {"home": {"meta_title": "DCX | File publique"}},
                "de": {"home": {"meta_title": "DCX | Offentliche Warteliste"}},
            }
        },
        "context": {
            "what_happened": "The backend returned the current live public UX-string bundle for Astro static generation.",
            "side_effects_executed": [],
            "next_steps": [
                "Continue the public build using the returned live bundle.",
            ],
            "related_operations": [
                "read_dcx_public_build_time_ux_strings_bundle_capability",
            ],
        },
    }


def test_build_time_ux_strings_bundle_route_rejects_missing_token() -> None:
    with patch.object(
        public_bundle_routes,
        "read_dcx_public_build_time_ux_strings_bundle_capability",
        side_effect=RuntimeError("API_PUBLIC_BUILD_TOKEN_REQUIRED"),
    ):
        response = client.get("/public/build-time/ux-strings-bundle")
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


def test_build_time_ux_strings_bundle_route_surfaces_database_unavailable() -> None:
    with patch.object(
        public_bundle_routes,
        "read_dcx_public_build_time_ux_strings_bundle_capability",
        side_effect=RuntimeError("API_PUBLIC_UX_STRINGS_DB_UNAVAILABLE"),
    ):
        response = client.get(
            "/public/build-time/ux-strings-bundle",
            headers={"X-DCX-Public-Build-Token": "top-secret-build-token"},
        )
        payload = response.json()

    assert response.status_code == 503
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_PUBLIC_UX_STRINGS_DB_UNAVAILABLE",
            "message": "The backend could not read the live public UX strings from the database.",
            "suggested_action": "Restore database connectivity and retry the public build.",
        },
    }
