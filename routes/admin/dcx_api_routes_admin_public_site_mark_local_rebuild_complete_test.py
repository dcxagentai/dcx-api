"""
CONTEXT:
This file verifies the admin local public-site rebuild-complete route.
It keeps the local-only publish simulation executable while auth is still in temporary
local-debug mode.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.admin.dcx_api_routes_admin_public_site_mark_local_rebuild_complete as mark_complete_routes

client = TestClient(app)


def test_mark_local_rebuild_complete_route_returns_payload_for_local_debug_admin_user_id() -> None:
    with patch.object(
        mark_complete_routes,
        "mark_dcx_admin_public_site_local_rebuild_complete_capability",
        return_value={
            "surface_key": "dcx_public",
            "completed_by_user_id": 5,
            "completed_at_ts_ms": 1770000000000,
            "last_publish_status": "local_manual_rebuild_completed",
            "last_publish_message": "Local public rebuild marked complete after manual dcx_public refresh.",
        },
    ):
        response = client.post(
            "/admin/publish/public-site/mark-local-rebuild-complete",
            params={"admin_user_id": 5},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["surface_key"] == "dcx_public"
    assert payload["data"]["last_publish_status"] == "local_manual_rebuild_completed"
