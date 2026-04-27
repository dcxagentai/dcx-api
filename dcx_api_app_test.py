"""
CONTEXT:
This file verifies the assembled FastAPI application for the DCX API workspace.
It keeps the root route and `/users/signup-email` HTTP boundary contracts executable.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.admin.dcx_api_routes_admin_content_emails_catalog as admin_emails_catalog_routes
import routes.admin.dcx_api_routes_admin_content_newsletter_sends_catalog as admin_newsletter_sends_catalog_routes
import routes.admin.dcx_api_routes_admin_content_emails_save_live_row as admin_emails_save_routes
import routes.admin.dcx_api_routes_admin_content_ux_strings_catalog as admin_ux_strings_catalog_routes
import routes.admin.dcx_api_routes_admin_content_ux_strings_save_live_row as admin_ux_strings_save_routes
import routes.admin.dcx_api_routes_admin_users_list as admin_users_list_routes
import routes.auth.dcx_api_routes_auth_app_ux_strings_bundle as auth_app_ux_bundle_routes
import routes.users.dcx_api_routes_users_me_account_settings as me_account_settings_routes
import routes.users.dcx_api_routes_users_me_account_summary as me_account_summary_routes
import routes.users.dcx_api_routes_users_me_file_object as me_file_object_routes
import routes.users.dcx_api_routes_users_me_message_attachment_file as me_message_attachment_file_routes
import routes.users.dcx_api_routes_users_me_messages_create as me_messages_create_routes
import routes.users.dcx_api_routes_users_me_messages_detail as me_messages_detail_routes
import routes.users.dcx_api_routes_users_me_messages_inbox as me_messages_inbox_routes
import routes.users.dcx_api_routes_users_signup_email as signup_email_routes
import routes.users.dcx_api_routes_users_signup_email_resend_otp as resend_otp_routes
import routes.users.dcx_api_routes_users_signup_email_verify_otp as verify_otp_routes

client = TestClient(app)
LOCAL_APP_ORIGIN_HEADERS = {"Origin": "http://localhost:5173"}
LOCAL_ADMIN_ORIGIN_HEADERS = {"Origin": "http://localhost:5174"}


def test_root_route_returns_minimal_placeholder_html() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '/static/dcx_logo.png' in response.text
    assert "auth/login/password" not in response.text


def test_root_route_allows_local_frontend_origin() -> None:
    response = client.get("/", headers={"Origin": "http://localhost:4321"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:4321"


def test_root_route_allows_local_app_origin() -> None:
    response = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_root_route_allows_local_admin_origin() -> None:
    response = client.get("/", headers={"Origin": "http://localhost:5174"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5174"


def test_auth_app_ux_strings_bundle_route_returns_requested_language_bundle() -> None:
    with patch.object(
        auth_app_ux_bundle_routes,
        "read_dcx_app_auth_ux_strings_bundle_capability",
        return_value={
            "language_code": "fr",
            "common": {"checking_session": "Verification de session..."},
            "login_page": {"page_title": "Connexion"},
            "password_reset_request_page": {"page_title": "Reinitialiser le mot de passe"},
            "password_set_page": {"page_title": "Mot de passe"},
        },
    ):
        response = client.get("/auth/app-ux-strings-bundle?language_code=fr")
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["language_code"] == "fr"
    assert payload["data"]["login_page"]["page_title"] == "Connexion"
    assert payload["context"]["view"] == "auth_ux_strings_bundle"


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
                    "email_communication_preference": "newsletters",
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


def test_admin_newsletter_sends_catalog_route_returns_payload_for_authenticated_admin_session() -> None:
    with patch.object(
        admin_newsletter_sends_catalog_routes,
        "read_authenticated_dcx_admin_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        admin_newsletter_sends_catalog_routes,
        "read_dcx_admin_newsletter_sends_catalog_capability",
        return_value={
            "newsletter_sends": [
                {
                    "email_send_id": 701,
                    "source_email_id": 101,
                    "email_key": "weekly-alpha",
                    "send_status": "sent",
                    "send_audience_type": "newsletters",
                    "scheduled_send_at_ts_ms": 1777000000000,
                    "send_started_at_ts_ms": 1777000001000,
                    "send_completed_at_ts_ms": 1777000005000,
                    "cancelled_at_ts_ms": None,
                    "created_at_ts_ms": 1776999990000,
                    "updated_at_ts_ms": 1777000005000,
                    "language_code": "en",
                    "total_recipient_count": 12,
                    "send_candidate_count": 10,
                    "skipped_recipient_count": 2,
                    "blocked_missing_translation_count": 1,
                    "pending_recipient_count": 0,
                    "sending_recipient_count": 0,
                    "sent_recipient_count": 10,
                    "delivered_recipient_count": 8,
                    "failed_recipient_count": 1,
                    "bounced_recipient_count": 1,
                    "complained_recipient_count": 0,
                    "cancelled_recipient_count": 0,
                    "tracked_link_count": 4,
                    "total_click_count": 7,
                    "unique_clicked_link_count": 3,
                }
            ],
            "total_send_count": 1,
        },
    ):
        response = client.get("/admin/content/newsletters/en/weekly-alpha/sends")
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["total_send_count"] == 1
    assert payload["data"]["newsletter_sends"][0]["delivered_recipient_count"] == 8
    assert payload["data"]["newsletter_sends"][0]["total_click_count"] == 7
    assert payload["context"]["view"] == "newsletter_sends_catalog"


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
            headers=LOCAL_ADMIN_ORIGIN_HEADERS,
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
        headers=LOCAL_ADMIN_ORIGIN_HEADERS,
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


def test_admin_ux_strings_save_live_row_route_rejects_unknown_browser_origin() -> None:
    response = client.post(
        "/admin/content/ux-strings/save-live-row",
        json={
            "ux_string_id": 101,
            "text": "Updated translated value",
        },
        headers={"Origin": "https://attacker.example"},
    )
    payload = response.json()

    assert response.status_code == 403
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_FRONTEND_ORIGIN_FORBIDDEN",
            "message": "This browser request did not come from an allowed DCX frontend origin.",
            "suggested_action": "Retry the request from an allowed DCX frontend origin.",
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
            headers=LOCAL_ADMIN_ORIGIN_HEADERS,
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
        headers=LOCAL_ADMIN_ORIGIN_HEADERS,
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
            "email_communication_preference": "newsletters",
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
                    "value": "no_email",
                    "label": "No email",
                },
                {
                    "value": "newsletters",
                    "label": "Newsletters",
                },
                {
                    "value": "all_email",
                    "label": "All email",
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
            "email_communication_preference": "all_email",
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
            "email_communication_preference": "all_email",
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
                    "value": "no_email",
                    "label": "No email",
                },
                {
                    "value": "newsletters",
                    "label": "Newsletters",
                },
                {
                    "value": "all_email",
                    "label": "All email",
                },
            ],
        },
    ):
        response = client.post(
            "/users/me/account-settings",
            json={
                "preferred_language_id": 2,
                "preferred_timezone_id": 2,
                "email_communication_preference": "all_email",
            },
            headers=LOCAL_APP_ORIGIN_HEADERS,
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["preferred_language"]["language_code"] == "es"
    assert payload["data"]["email_communication_preference"] == "all_email"
    assert payload["context"]["operation"] == "account_settings_saved"


def test_users_me_account_settings_route_returns_auth_required_without_authenticated_session() -> None:
    response = client.post(
        "/users/me/account-settings",
        json={
            "preferred_language_id": 1,
            "preferred_timezone_id": 2,
            "email_communication_preference": "newsletters",
        },
        headers=LOCAL_APP_ORIGIN_HEADERS,
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


def test_users_me_messages_inbox_route_returns_messages_payload_for_authenticated_session() -> None:
    with patch.object(
        me_messages_inbox_routes,
        "read_authenticated_dcx_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        me_messages_inbox_routes,
        "read_authenticated_dcx_user_messages_inbox",
        return_value={
            "messages": [
                {
                    "message_id": 901,
                    "channel_type": "app",
                    "provider_type": "dcx_app",
                    "message_direction": "inbound",
                    "message_format": "text",
                    "message_subject": "",
                    "raw_text_content": "Hola, vendo trigo.",
                    "derived_text_content": "Hola, vendo trigo.",
                    "analysis_summary_text": "The user is offering wheat in Spanish.",
                    "processing_status": "ready",
                    "derivation_status": "completed",
                    "detected_language_code": "es",
                    "received_at_ts_ms": 1777000000000,
                    "created_at_ts_ms": 1777000000000,
                }
            ],
            "selected_filter": "text",
            "total_message_count": 1,
        },
    ):
        response = client.get("/users/me/messages?message_format_filter=text", headers=LOCAL_APP_ORIGIN_HEADERS)
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["total_message_count"] == 1
    assert payload["data"]["messages"][0]["message_id"] == 901
    assert payload["context"]["view"] == "messages_inbox"


def test_users_me_messages_create_route_returns_message_detail_for_authenticated_session() -> None:
    captured_creation_kwargs: dict = {}

    def _capture_create_authenticated_dcx_app_contact_message(**kwargs):
        captured_creation_kwargs.update(kwargs)
        return {
            "message_id": 901,
            "job_id": 3001,
            "processing_status": "ready",
            "derivation_status": "completed",
        }

    with patch.object(
        me_messages_create_routes,
        "read_authenticated_dcx_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        me_messages_create_routes,
        "create_authenticated_dcx_app_contact_message",
        side_effect=_capture_create_authenticated_dcx_app_contact_message,
    ), patch.object(
        me_messages_create_routes,
        "read_authenticated_dcx_user_contact_message_detail",
        return_value={
            "message_id": 901,
            "channel_type": "app",
            "provider_type": "dcx_app",
            "message_direction": "inbound",
            "message_format": "text",
            "message_subject": "",
            "raw_text_content": "Hola, vendo trigo.",
            "derived_text_content": "Hola, vendo trigo.",
            "analysis_summary_text": "The user is offering wheat in Spanish.",
            "processing_status": "ready",
            "derivation_status": "completed",
            "detected_language_code": "es",
            "received_at_ts_ms": 1777000000000,
            "created_at_ts_ms": 1777000000000,
            "updated_at_ts_ms": 1777000001000,
            "attachments": [],
        },
    ):
        response = client.post(
            "/users/me/messages",
            data={"message_text": "Hola, vendo trigo."},
            files=[("message_files", ("offer.pdf", b"pdf-bytes", "application/pdf"))],
            headers=LOCAL_APP_ORIGIN_HEADERS,
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["message_id"] == 901
    assert payload["context"]["operation"] == "message_created_ready"
    assert captured_creation_kwargs["authenticated_user_id"] == 1
    assert captured_creation_kwargs["message_text"] == "Hola, vendo trigo."
    assert len(captured_creation_kwargs["attachment_inputs"]) == 1
    assert captured_creation_kwargs["attachment_inputs"][0]["original_filename"] == "offer.pdf"
    assert captured_creation_kwargs["attachment_inputs"][0]["content_type"] == "application/pdf"
    assert captured_creation_kwargs["attachment_inputs"][0]["file_bytes"] == b"pdf-bytes"


def test_users_me_message_detail_route_returns_message_for_authenticated_session() -> None:
    with patch.object(
        me_messages_detail_routes,
        "read_authenticated_dcx_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        me_messages_detail_routes,
        "read_authenticated_dcx_user_contact_message_detail",
        return_value={
            "message_id": 901,
            "channel_type": "app",
            "provider_type": "dcx_app",
            "message_direction": "inbound",
            "message_format": "text",
            "message_subject": "",
            "raw_text_content": "Hola, vendo trigo.",
            "derived_text_content": "Hola, vendo trigo.",
            "analysis_summary_text": "The user is offering wheat in Spanish.",
            "processing_status": "ready",
            "derivation_status": "completed",
            "detected_language_code": "es",
            "received_at_ts_ms": 1777000000000,
            "created_at_ts_ms": 1777000000000,
            "updated_at_ts_ms": 1777000001000,
            "attachments": [],
        },
    ):
        response = client.get("/users/me/messages/901", headers=LOCAL_APP_ORIGIN_HEADERS)
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["message_id"] == 901
    assert payload["context"]["view"] == "message_detail"


def test_users_me_message_attachment_file_route_returns_stream_for_authenticated_session() -> None:
    with patch.object(
        me_message_attachment_file_routes,
        "read_authenticated_dcx_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        me_message_attachment_file_routes,
        "read_authenticated_dcx_user_contact_message_attachment_stream",
        return_value={
            "content_bytes": b"image-bytes",
            "content_type": "image/png",
            "original_filename": "offer.png",
            "file_kind": "image",
        },
    ):
        response = client.get(
            "/users/me/messages/901/attachments/77/file",
            headers=LOCAL_APP_ORIGIN_HEADERS,
        )

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"] == "image/png"
    assert "cross-origin-resource-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_users_me_message_attachment_file_route_allows_media_element_request_without_origin() -> None:
    with patch.object(
        me_message_attachment_file_routes,
        "read_authenticated_dcx_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        me_message_attachment_file_routes,
        "read_authenticated_dcx_user_contact_message_attachment_stream",
        return_value={
            "content_bytes": b"image-bytes",
            "content_type": "image/jpeg",
            "original_filename": "whatsapp-image.jpg",
            "file_kind": "image",
        },
    ):
        response = client.get("/users/me/messages/901/attachments/77/file")

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"] == "image/jpeg"


def test_users_me_file_object_route_returns_stream_for_authenticated_session() -> None:
    with patch.object(
        me_file_object_routes,
        "read_authenticated_dcx_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        me_file_object_routes,
        "read_authenticated_dcx_user_file_object_stream_by_file_uuid",
        return_value={
            "content_bytes": b"image-bytes",
            "content_type": "image/png",
            "original_filename": "offer.png",
            "file_kind": "image",
        },
    ):
        response = client.get(
            "/users/me/files/00000000-0000-0000-0000-000000000801",
            headers=LOCAL_APP_ORIGIN_HEADERS,
        )

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"] == "image/png"
    assert "cross-origin-resource-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_users_me_file_object_route_allows_media_element_request_without_origin() -> None:
    with patch.object(
        me_file_object_routes,
        "read_authenticated_dcx_user_id_or_error_response",
        return_value=(1, "session_cookie", None),
    ), patch.object(
        me_file_object_routes,
        "read_authenticated_dcx_user_file_object_stream_by_file_uuid",
        return_value={
            "content_bytes": b"audio-bytes",
            "content_type": "audio/ogg",
            "original_filename": "voice-note.ogg",
            "file_kind": "audio",
        },
    ):
        response = client.get("/users/me/files/00000000-0000-0000-0000-000000000802")

    assert response.status_code == 200
    assert response.content == b"audio-bytes"
    assert response.headers["content-type"] == "audio/ogg"


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
