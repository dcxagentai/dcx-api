"""
CONTEXT:
This file verifies the admin public-site publish-status route.
It keeps the first manual public deploy loop executable under the real authenticated admin/dev
session boundary.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.admin.dcx_api_routes_admin_public_site_publish_status as publish_status_routes

client = TestClient(app)


def test_public_site_publish_status_route_returns_payload_for_authenticated_admin_session() -> None:
    with patch.object(
        publish_status_routes,
        "read_authenticated_dcx_admin_user_id_or_error_response",
        return_value=(5, "session_cookie", None),
    ), patch.object(
        publish_status_routes,
        "read_dcx_admin_public_site_publish_status_capability",
        return_value={
            "surface_key": "dcx_public",
            "last_successful_publish_at_ts_ms": 1770000000000,
            "last_successful_publish_by_user_id": 5,
            "last_attempted_publish_at_ts_ms": 1770000000000,
            "last_attempted_publish_by_user_id": 5,
            "last_publish_status": "trigger_accepted",
            "last_publish_message": "Cloudflare Pages deploy hook accepted the publish request.",
            "created_at_ts_ms": 1769000000000,
            "updated_at_ts_ms": 1770000000000,
            "pending_change_count": 2,
            "pending_changes_preview": [],
            "public_managed_content_kinds": ["ux_strings", "content_pages"],
            "public_managed_groups": ["home", "signup_form"],
        },
    ):
        response = client.get("/admin/publish/public-site/status")
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["surface_key"] == "dcx_public"
    assert payload["data"]["pending_change_count"] == 2


def test_public_site_publish_status_route_rejects_missing_admin_session() -> None:
    with patch.object(
        publish_status_routes,
        "read_authenticated_dcx_admin_user_id_or_error_response",
        return_value=(
            None,
            "session_cookie",
            JSONResponse(
                status_code=401,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_DCX_ADMIN_AUTH_REQUIRED",
                        "message": "Sign in again.",
                        "suggested_action": "Use the admin login page.",
                    },
                },
            ),
        ),
    ):
        response = client.get("/admin/publish/public-site/status")
        payload = response.json()

    assert response.status_code == 401
    assert payload["ok"] is False
    assert payload["error"]["code"] == "API_DCX_ADMIN_AUTH_REQUIRED"
