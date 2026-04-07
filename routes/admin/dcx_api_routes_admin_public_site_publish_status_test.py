"""
CONTEXT:
This file verifies the admin public-site publish-status route.
It keeps the first manual public deploy loop executable while auth is still in temporary
local-debug mode.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.admin.dcx_api_routes_admin_public_site_publish_status as publish_status_routes

client = TestClient(app)


def test_public_site_publish_status_route_returns_payload_for_local_debug_admin_user_id() -> None:
    with patch.object(
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
            "public_managed_groups": ["home", "signup_form"],
        },
    ):
        response = client.get("/admin/publish/public-site/status", params={"admin_user_id": 5})
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["surface_key"] == "dcx_public"
    assert payload["data"]["pending_change_count"] == 2
