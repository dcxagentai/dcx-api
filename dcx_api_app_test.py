"""
CONTEXT:
This file verifies the assembled FastAPI application for the DCX API workspace.
It keeps the root route and `/users/signup-email` HTTP boundary contracts executable.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.users.dcx_api_users_signup_email_routes as users_signup_routes

client = TestClient(app)


def test_root_route_returns_minimal_ready_payload() -> None:
    response = client.get("/")
    payload = response.json()

    assert response.status_code == 200
    assert payload == {
        "ok": True,
        "data": {
            "service_name": "dcx_api",
            "status": "ready",
            "message": "DCX API is ready.",
        },
        "context": {
            "what_happened": "The backend root route responded successfully with a minimal service-ready payload.",
            "side_effects_executed": [],
            "next_steps": [
                "Use the dedicated /users routes for public signup flow interactions.",
                "Add dedicated readiness and health routes when deployment needs them.",
            ],
            "related_operations": [
                "dcx_api_users_signup_email_router",
            ],
        },
    }


def test_root_route_allows_local_frontend_origin() -> None:
    response = client.get("/", headers={"Origin": "http://localhost:4321"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:4321"


def test_users_email_signup_route_returns_minimal_flow_token_payload() -> None:
    with patch.object(
        users_signup_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        users_signup_routes,
        "create_or_refresh_public_email_signup_artifacts_capability",
        return_value={
            "signup_flow_token": "opaque_signup_flow_token_value_123456",
            "send_required": True,
            "challenge_id": 301,
            "email_delivery_draft": {
                "recipient_email": "user@example.com",
                "subject": "Your DCX access code",
                "text_body": "Hello",
            },
        },
    ), patch.object(
        users_signup_routes,
        "send_public_email_signup_otp_via_resend_capability",
        return_value={"provider": "resend", "status": "accepted", "challenge_id": 301},
    ):
        response = client.post(
            "/users/signup-email",
            json={
                "email": "user@example.com",
                "language_code": "en",
                "signup_page_url": "http://localhost:4321/",
            },
            headers={"Origin": "http://localhost:4321"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"] == {
        "signup_flow_token": "opaque_signup_flow_token_value_123456",
    }


def test_users_email_signup_route_rejects_extra_fields() -> None:
    response = client.post(
        "/users/signup-email",
        json={
            "email": "user@example.com",
            "language_code": "en",
            "signup_page_url": "http://localhost:4321/",
            "debug": True,
        },
        headers={"Origin": "http://localhost:4321"},
    )

    assert response.status_code == 422


def test_users_email_signup_route_returns_generic_error_wrapper_on_validation_failure() -> None:
    with patch.object(
        users_signup_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        users_signup_routes,
        "create_or_refresh_public_email_signup_artifacts_capability",
        side_effect=RuntimeError("API_PUBLIC_EMAIL_SIGNUP_EMAIL_INVALID"),
    ):
        response = client.post(
            "/users/signup-email",
            json={
                "email": "not-an-email",
                "language_code": "en",
                "signup_page_url": "http://localhost:4321/",
            },
            headers={"Origin": "http://localhost:4321"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_PUBLIC_EMAIL_SIGNUP_REQUEST_INVALID",
            "message": "We could not accept that signup request.",
            "suggested_action": "Check the form input and try again.",
        },
    }


def test_users_email_verify_route_returns_generic_failure_wrapper() -> None:
    with patch.object(
        users_signup_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        users_signup_routes,
        "verify_public_email_signup_otp_capability",
        side_effect=RuntimeError("API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED"),
    ):
        response = client.post(
            "/users/signup-email/verify-otp",
            json={
                "signup_flow_token": "opaque_signup_flow_token_value_123456",
                "otp_code": "123456",
                "language_code": "en",
                "verification_page_url": "http://localhost:4321/users/signup-email/verify-otp",
            },
            headers={"Origin": "http://localhost:4321"},
        )
        payload = response.json()

    assert payload == {
        "ok": False,
        "error": {
            "code": "API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED",
            "message": "We could not verify that code.",
            "suggested_action": "Request a new code or restart the signup flow.",
        },
    }


def test_users_email_resend_route_returns_refreshed_flow_token() -> None:
    with patch.object(
        users_signup_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        users_signup_routes,
        "resend_public_email_signup_otp_capability",
        return_value={
            "status": "otp_resent",
            "signup_flow_token": "new_opaque_signup_flow_token_value_654321",
            "challenge_id": 301,
            "email_delivery_draft": {
                "recipient_email": "user@example.com",
                "subject": "Your DCX access code",
                "text_body": "Hello",
            },
        },
    ), patch.object(
        users_signup_routes,
        "send_public_email_signup_otp_via_resend_capability",
        return_value={"provider": "resend", "status": "accepted", "challenge_id": 301},
    ):
        response = client.post(
            "/users/signup-email/resend-otp",
            json={
                "signup_flow_token": "opaque_signup_flow_token_value_123456",
                "language_code": "en",
                "resend_page_url": "http://localhost:4321/users/signup-email/verify-otp",
            },
            headers={"Origin": "http://localhost:4321"},
        )
        payload = response.json()

    assert payload["ok"] is True
    assert payload["data"] == {
        "signup_flow_token": "new_opaque_signup_flow_token_value_654321",
    }
