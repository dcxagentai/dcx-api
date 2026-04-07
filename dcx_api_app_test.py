"""
CONTEXT:
This file verifies the assembled FastAPI application for the DCX API workspace.
It keeps the root route and `/users/signup-email` HTTP boundary contracts executable.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.admin.dcx_api_routes_admin_content_emails_catalog as admin_emails_catalog_routes
import routes.admin.dcx_api_routes_admin_content_emails_save_live_row as admin_emails_save_routes
import routes.admin.dcx_api_routes_admin_content_ux_strings_catalog as admin_ux_strings_catalog_routes
import routes.admin.dcx_api_routes_admin_content_ux_strings_save_live_row as admin_ux_strings_save_routes
import routes.admin.dcx_api_routes_admin_users_list as admin_users_list_routes
import routes.users.dcx_api_routes_users_me_account_settings as me_account_settings_routes
import routes.users.dcx_api_routes_users_me_account_summary as me_account_summary_routes
import routes.users.dcx_api_routes_users_signup_email as signup_email_routes
import routes.users.dcx_api_routes_users_signup_email_resend_otp as resend_otp_routes
import routes.users.dcx_api_routes_users_signup_email_verify_otp as verify_otp_routes

client = TestClient(app)


def test_root_route_returns_minimal_ready_payload() -> None:
    response = client.get("/")
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"] == {
        "service_name": "dcx_api",
        "status": "ready",
        "message": "DCX API is ready.",
    }
    assert payload["context"]["what_happened"] == (
        "The backend root route responded successfully with a minimal service-ready payload."
    )
    assert payload["context"]["side_effects_executed"] == []
    assert "Use /auth/password/request-reset to start the email reset flow." in payload["context"]["next_steps"]
    assert (
        "Use /auth/password/complete-set to finish password setup or reset from the one-time token."
        in payload["context"]["next_steps"]
    )
    assert "dcx_api_routes_auth_password_request_reset_router" in payload["context"]["related_operations"]
    assert "dcx_api_routes_auth_password_complete_set_router" in payload["context"]["related_operations"]


def test_root_route_allows_local_frontend_origin() -> None:
    response = client.get("/", headers={"Origin": "http://localhost:4321"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:4321"


def test_root_route_allows_local_app_origin() -> None:
    response = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_root_route_allows_local_admin_origin() -> None:
    response = client.get("/", headers={"Origin": "http://localhost:5174"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5174"


def test_admin_users_list_route_returns_users_payload_for_authenticated_admin_session() -> None:
    with patch.object(
        admin_users_list_routes,
        "read_authenticated_dcx_admin_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        admin_users_list_routes,
        "read_dcx_admin_user_list_capability",
        return_value={
            "users": [
                {
                    "user_id": 1,
                    "user_uuid": "caa94290-93cc-4fea-89ac-a4db936d5c8b",
                    "primary_email": "matbenet77@gmail.com",
                    "primary_email_confirmed": True,
                    "primary_email_confirmed_at_ts_ms": 1775324331389,
                    "account_status": "confirmed",
                    "email_communication_preference": "announcements",
                    "last_seen_at_ts_ms": 1775324331389,
                    "created_at_ts_ms": 1773936459277,
                    "updated_at_ts_ms": 1775324331563,
                    "preferred_language": {
                        "id": 4,
                        "language_code": "de",
                        "language_name_en": "German",
                        "language_name_native": "Deutsch",
                        "is_rtl": False,
                    },
                }
            ],
            "total_user_count": 1,
        },
    ):
        response = client.get("/admin/users/list")
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["total_user_count"] == 1
    assert payload["context"]["identity_resolution_mode"] == "session_cookie"


def test_admin_users_list_route_returns_auth_required_without_authenticated_session() -> None:
    response = client.get("/admin/users/list")
    payload = response.json()

    assert response.status_code == 401
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_ADMIN_AUTH_REQUIRED",
            "message": "No authenticated DCX admin session is active.",
            "suggested_action": "Sign in as an admin/dev user, then retry.",
        },
    }


def test_admin_ux_strings_catalog_route_returns_payload_for_authenticated_admin_session() -> None:
    with patch.object(
        admin_ux_strings_catalog_routes,
        "read_authenticated_dcx_admin_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        admin_ux_strings_catalog_routes,
        "read_dcx_admin_live_ux_strings_catalog_capability",
        return_value={
            "ux_strings": [
                {
                    "ux_string_id": 101,
                    "string_group": "signup_otp_form",
                    "string_key": "restart_message",
                    "text": "This verification session has expired.",
                    "is_original": True,
                    "is_live": True,
                    "version_of_id": None,
                    "translation_of_id": None,
                    "created_at_ts_ms": 1775318000000,
                    "updated_at_ts_ms": 1775318000100,
                    "language": {
                        "id": 1,
                        "language_code": "en",
                        "language_name_en": "English",
                        "language_name_native": "English",
                        "is_rtl": False,
                    },
                }
            ],
            "total_live_row_count": 1,
        },
    ):
        response = client.get("/admin/content/ux-strings/catalog")
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["total_live_row_count"] == 1
    assert payload["context"]["view"] == "ux_strings_catalog"


def test_admin_emails_catalog_route_returns_payload_for_authenticated_admin_session() -> None:
    with patch.object(
        admin_emails_catalog_routes,
        "read_authenticated_dcx_admin_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        admin_emails_catalog_routes,
        "read_dcx_admin_live_emails_catalog_capability",
        return_value={
            "emails": [
                {
                    "email_id": 1,
                    "email_type": "transactional",
                    "email_key": "signup_verify_otp",
                    "email_subject": "DCX Agentic: Your verification code",
                    "email_body": "Your code is {{ otp_code }}",
                    "is_original": True,
                    "is_live": True,
                    "version_of_id": None,
                    "translation_of_id": None,
                    "created_at_ts_ms": 1775319000000,
                    "updated_at_ts_ms": 1775319000100,
                    "language": {
                        "id": 1,
                        "language_code": "en",
                        "language_name_en": "English",
                        "language_name_native": "English",
                        "is_rtl": False,
                    },
                }
            ],
            "total_live_row_count": 1,
        },
    ):
        response = client.get("/admin/content/emails/catalog")
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["total_live_row_count"] == 1
    assert payload["context"]["view"] == "emails_catalog"


def test_admin_ux_strings_save_live_row_route_returns_save_result_for_authenticated_admin_session() -> None:
    with patch.object(
        admin_ux_strings_save_routes,
        "read_authenticated_dcx_admin_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        admin_ux_strings_save_routes,
        "save_dcx_admin_live_ux_string_row_version_capability",
        return_value={
            "ux_string_id": 202,
            "previous_ux_string_id": 101,
            "was_noop": False,
        },
    ):
        response = client.post(
            "/admin/content/ux-strings/save-live-row",
            json={
                "ux_string_id": 101,
                "text": "Updated translated value",
            },
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["ux_string_id"] == 202
    assert payload["context"]["operation"] == "live_row_saved"


def test_admin_ux_strings_save_live_row_route_returns_auth_required_without_authenticated_session() -> None:
    response = client.post(
        "/admin/content/ux-strings/save-live-row",
        json={
            "ux_string_id": 101,
            "text": "Updated translated value",
        },
    )
    payload = response.json()

    assert response.status_code == 401
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_ADMIN_AUTH_REQUIRED",
            "message": "No authenticated DCX admin session is active.",
            "suggested_action": "Sign in as an admin/dev user, then retry.",
        },
    }


def test_admin_emails_save_live_row_route_returns_save_result_for_authenticated_admin_session() -> None:
    with patch.object(
        admin_emails_save_routes,
        "read_authenticated_dcx_admin_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        admin_emails_save_routes,
        "save_dcx_admin_live_email_row_version_capability",
        return_value={
            "email_id": 22,
            "previous_email_id": 11,
            "was_noop": False,
        },
    ):
        response = client.post(
            "/admin/content/emails/save-live-row",
            json={
                "email_id": 11,
                "email_subject": "DCX Agentic: Ihr Bestätigungscode",
                "email_body": "Code: {{ otp_code }}\nLink: {{ verify_otp_url }}",
            },
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["email_id"] == 22
    assert payload["context"]["operation"] == "live_row_saved"


def test_admin_emails_save_live_row_route_returns_auth_required_without_authenticated_session() -> None:
    response = client.post(
        "/admin/content/emails/save-live-row",
        json={
            "email_id": 11,
            "email_subject": "DCX Agentic: Ihr Bestätigungscode",
            "email_body": "Code: {{ otp_code }}\nLink: {{ verify_otp_url }}",
        },
    )
    payload = response.json()

    assert response.status_code == 401
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_ADMIN_AUTH_REQUIRED",
            "message": "No authenticated DCX admin session is active.",
            "suggested_action": "Sign in as an admin/dev user, then retry.",
        },
    }


def test_users_me_account_summary_route_returns_account_payload_for_authenticated_session() -> None:
    with patch.object(
        me_account_summary_routes,
        "read_authenticated_dcx_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        me_account_summary_routes,
        "read_authenticated_dcx_user_account_summary_capability",
        return_value={
            "user_id": 1,
            "user_uuid": "caa94290-93cc-4fea-89ac-a4db936d5c8b",
            "primary_email": "matbenet77@gmail.com",
            "primary_email_confirmed": True,
            "primary_email_confirmed_at_ts_ms": 1775324331389,
            "primary_phone_e164": "+34600000001",
            "primary_phone_confirmed": True,
            "primary_phone_confirmed_at_ts_ms": 1775324300000,
            "primary_phone_channel": "whatsapp",
            "account_status": "confirmed",
            "email_communication_preference": "announcements",
            "last_seen_at_ts_ms": 1775324331389,
            "created_at_ts_ms": 1773936459277,
            "updated_at_ts_ms": 1775324331563,
            "preferred_language": {
                "id": 4,
                "language_code": "de",
                "language_name_en": "German",
                "language_name_native": "Deutsch",
                "is_rtl": False,
            },
            "preferred_timezone": {
                "id": 2,
                "iana_name": "Europe/Madrid",
                "display_label": "(UTC+1/+2) Madrid",
                "region_label": "Europe",
            },
            "available_languages": [
                {
                    "id": 1,
                    "language_code": "en",
                    "language_name_en": "English",
                    "language_name_native": "English",
                    "is_rtl": False,
                },
                {
                    "id": 4,
                    "language_code": "de",
                    "language_name_en": "German",
                    "language_name_native": "Deutsch",
                    "is_rtl": False,
                },
            ],
            "available_timezones": [
                {
                    "id": 1,
                    "iana_name": "Europe/London",
                    "display_label": "(UTC+0/+1) London",
                    "region_label": "Europe",
                },
                {
                    "id": 2,
                    "iana_name": "Europe/Madrid",
                    "display_label": "(UTC+1/+2) Madrid",
                    "region_label": "Europe",
                },
            ],
            "available_email_communication_preferences": [
                {
                    "value": "announcements",
                    "label": "Announcements",
                },
                {
                    "value": "essential_only",
                    "label": "Essential only",
                },
            ],
        },
    ):
        response = client.get("/users/me/account-summary")
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["primary_email"] == "matbenet77@gmail.com"
    assert payload["context"]["identity_resolution_mode"] == "session_cookie"


def test_users_me_account_summary_route_returns_auth_required_without_authenticated_session() -> None:
    response = client.get("/users/me/account-summary")
    payload = response.json()

    assert response.status_code == 401
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_AUTH_SESSION_REQUIRED",
            "message": "No authenticated DCX app session is active.",
            "suggested_action": "Sign in through the DCX app login flow, then retry.",
        },
    }


def test_users_me_account_settings_route_saves_and_returns_refreshed_account_payload_for_authenticated_session() -> None:
    with patch.object(
        me_account_settings_routes,
        "read_authenticated_dcx_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        me_account_settings_routes,
        "save_authenticated_dcx_user_account_editable_settings_capability",
        return_value={
            "user_id": 1,
            "preferred_language_id": 2,
            "preferred_timezone_id": 2,
            "email_communication_preference": "essential_only",
        },
    ), patch.object(
        me_account_settings_routes,
        "read_authenticated_dcx_user_account_summary_capability",
        return_value={
            "user_id": 1,
            "user_uuid": "caa94290-93cc-4fea-89ac-a4db936d5c8b",
            "primary_email": "matbenet77@gmail.com",
            "primary_email_confirmed": True,
            "primary_email_confirmed_at_ts_ms": 1775324331389,
            "primary_phone_e164": "+34600000001",
            "primary_phone_confirmed": True,
            "primary_phone_confirmed_at_ts_ms": 1775324300000,
            "primary_phone_channel": "whatsapp",
            "account_status": "confirmed",
            "email_communication_preference": "essential_only",
            "last_seen_at_ts_ms": 1775324331389,
            "created_at_ts_ms": 1773936459277,
            "updated_at_ts_ms": 1775325000000,
            "preferred_language": {
                "id": 2,
                "language_code": "es",
                "language_name_en": "Spanish",
                "language_name_native": "Español",
                "is_rtl": False,
            },
            "preferred_timezone": {
                "id": 2,
                "iana_name": "Europe/Madrid",
                "display_label": "(UTC+1/+2) Madrid",
                "region_label": "Europe",
            },
            "available_languages": [
                {
                    "id": 1,
                    "language_code": "en",
                    "language_name_en": "English",
                    "language_name_native": "English",
                    "is_rtl": False,
                },
                {
                    "id": 2,
                    "language_code": "es",
                    "language_name_en": "Spanish",
                    "language_name_native": "Español",
                    "is_rtl": False,
                },
            ],
            "available_timezones": [
                {
                    "id": 1,
                    "iana_name": "Europe/London",
                    "display_label": "(UTC+0/+1) London",
                    "region_label": "Europe",
                },
                {
                    "id": 2,
                    "iana_name": "Europe/Madrid",
                    "display_label": "(UTC+1/+2) Madrid",
                    "region_label": "Europe",
                },
            ],
            "available_email_communication_preferences": [
                {
                    "value": "announcements",
                    "label": "Announcements",
                },
                {
                    "value": "essential_only",
                    "label": "Essential only",
                },
            ],
        },
    ):
        response = client.post(
            "/users/me/account-settings",
            json={
                "preferred_language_id": 2,
                "preferred_timezone_id": 2,
                "email_communication_preference": "essential_only",
            },
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["preferred_language"]["language_code"] == "es"
    assert payload["data"]["email_communication_preference"] == "essential_only"
    assert payload["context"]["operation"] == "account_settings_saved"


def test_users_me_account_settings_route_returns_auth_required_without_authenticated_session() -> None:
    response = client.post(
        "/users/me/account-settings",
        json={
            "preferred_language_id": 1,
            "preferred_timezone_id": 2,
            "email_communication_preference": "announcements",
        },
    )
    payload = response.json()

    assert response.status_code == 401
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_AUTH_SESSION_REQUIRED",
            "message": "No authenticated DCX app session is active.",
            "suggested_action": "Sign in through the DCX app login flow, then retry.",
        },
    }


def test_users_email_signup_route_returns_minimal_flow_token_payload() -> None:
    with patch.object(
        signup_email_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        signup_email_routes,
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
        signup_email_routes,
        "send_public_email_signup_otp",
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
        signup_email_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        signup_email_routes,
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
        verify_otp_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        verify_otp_routes,
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


def test_users_email_verify_route_sends_confirmation_email_but_keeps_browser_payload_minimal() -> None:
    with patch.object(
        verify_otp_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        verify_otp_routes,
        "verify_public_email_signup_otp_capability",
        return_value={
            "status": "confirmed",
            "confirmed_email": "user@example.com",
            "language_code": "en",
            "verification_page_url": "http://localhost:4321/users/signup-email/verify-otp",
        },
    ), patch.object(
        verify_otp_routes,
        "build_public_email_signup_confirmation_email_delivery_draft",
        return_value={
            "recipient_email": "user@example.com",
            "subject": "You're on the DCX Agentic waitlist",
            "text_body": "Hello",
        },
    ), patch.object(
        verify_otp_routes,
        "send_public_email_signup_confirmation",
        return_value={"provider": "resend", "status": "accepted", "confirmed_email": "user@example.com"},
    ), patch.object(
        verify_otp_routes,
        "create_dcx_password_setup_link_after_confirmed_signup",
        return_value={
            "password_set_url": "http://localhost:5173/password/set?mode=password_setup#password_challenge_token=test-token"
        },
    ) as confirmation_send_mock:
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

    confirmation_send_mock.assert_called_once()
    assert payload == {
        "ok": True,
        "data": {
            "next_step_url": "http://localhost:5173/password/set?mode=password_setup#password_challenge_token=test-token",
        },
    }


def test_users_email_verify_route_ignores_confirmation_email_delivery_failure() -> None:
    with patch.object(
        verify_otp_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        verify_otp_routes,
        "verify_public_email_signup_otp_capability",
        return_value={
            "status": "confirmed",
            "confirmed_email": "user@example.com",
            "language_code": "en",
            "verification_page_url": "http://localhost:4321/users/signup-email/verify-otp",
        },
    ), patch.object(
        verify_otp_routes,
        "build_public_email_signup_confirmation_email_delivery_draft",
        return_value={
            "recipient_email": "user@example.com",
            "subject": "You're on the DCX Agentic waitlist",
            "text_body": "Hello",
        },
    ), patch.object(
        verify_otp_routes,
        "send_public_email_signup_confirmation",
        side_effect=RuntimeError("API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED"),
    ), patch.object(
        verify_otp_routes,
        "create_dcx_password_setup_link_after_confirmed_signup",
        return_value={
            "password_set_url": "http://localhost:5173/password/set?mode=password_setup#password_challenge_token=test-token"
        },
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
        "ok": True,
        "data": {
            "next_step_url": "http://localhost:5173/password/set?mode=password_setup#password_challenge_token=test-token",
        },
    }


def test_users_email_resend_route_returns_refreshed_flow_token() -> None:
    with patch.object(
        resend_otp_routes,
        "enforce_public_route_rate_limit_capability",
        return_value={"request_count": 1},
    ), patch.object(
        resend_otp_routes,
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
        resend_otp_routes,
        "send_public_email_signup_otp",
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
