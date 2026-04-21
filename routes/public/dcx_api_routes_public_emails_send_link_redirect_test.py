"""
CONTEXT:
This file verifies the public tracked-email-link redirect route for DCX.
It keeps the redirect behavior and canonical error wrapper executable while the email worker grows.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.public.dcx_api_routes_public_emails_send_link_redirect as public_email_link_redirect_routes

client = TestClient(app)


def test_tracked_email_link_route_redirects_for_valid_token() -> None:
    with patch.object(
        public_email_link_redirect_routes,
        "record_dcx_email_send_link_click_and_read_redirect_target_capability",
        return_value={
            "click_id": 9001,
            "email_send_id": 501,
            "email_send_link_id": 31,
            "original_url": "https://dcxagent.ai/market",
            "tracking_token": "track-123",
            "clicked_at_ts_ms": 1778000000000,
        },
    ) as capability_mock:
        response = client.get(
            "/public/email-links/track-123",
            headers={"User-Agent": "DCX Test Browser"},
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == "https://dcxagent.ai/market"
    assert response.headers["cache-control"] == "no-store"
    capability_mock.assert_called_once_with(
        tracking_token="track-123",
        request_ip="testclient",
        request_user_agent="DCX Test Browser",
    )


def test_tracked_email_link_route_returns_not_found_for_unknown_token() -> None:
    with patch.object(
        public_email_link_redirect_routes,
        "record_dcx_email_send_link_click_and_read_redirect_target_capability",
        side_effect=RuntimeError("API_DCX_EMAIL_SEND_LINK_REDIRECT_NOT_FOUND"),
    ):
        response = client.get("/public/email-links/missing-token", follow_redirects=False)
        payload = response.json()

    assert response.status_code == 404
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_EMAIL_SEND_LINK_REDIRECT_NOT_FOUND",
            "message": "We could not resolve that tracked email link.",
            "suggested_action": "Retry from the original email once the tracked link is valid and the backend is healthy.",
        },
    }
