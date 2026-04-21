"""
CONTEXT:
This file verifies the public DCX email unsubscribe route.
It keeps the human-facing confirmation and error pages executable while the email system grows.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.public.dcx_api_routes_public_email_preferences_unsubscribe as public_email_unsubscribe_routes

client = TestClient(app)


def test_public_unsubscribe_route_returns_confirmation_page_for_valid_request() -> None:
    with patch.object(
        public_email_unsubscribe_routes,
        "apply_dcx_public_email_unsubscribe_request_capability",
        return_value={
            "user_id": 7,
            "recipient_email": "alpha@example.com",
            "unsubscribe_kind": "promotional",
            "email_communication_preference": "newsletters",
            "newsletters_suppressed": False,
        },
    ):
        response = client.get(
            "/public/email-preferences/unsubscribe/promotional/token-value",
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert "Preference updated" in response.text
    assert "campaigns or promotional sequences" in response.text


def test_public_unsubscribe_route_returns_error_page_for_invalid_request() -> None:
    with patch.object(
        public_email_unsubscribe_routes,
        "apply_dcx_public_email_unsubscribe_request_capability",
        side_effect=RuntimeError("API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_INVALID"),
    ):
        response = client.get(
            "/public/email-preferences/unsubscribe/all/bad-token",
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "We could not update your email preferences" in response.text
