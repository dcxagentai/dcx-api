"""
CONTEXT:
This file is the composition root for the DCX API workspace.
It exists to assemble middleware, a quiet branded root route, and the dedicated route modules
while keeping HTTP route bodies out of the app root.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from routes.files.dcx_api_routes_files_r2_hello_world import (
    dcx_api_routes_files_r2_hello_world_router,
)
from routes.public.dcx_api_routes_public_build_time_api_test import (
    dcx_api_routes_public_build_time_api_test_router,
)
from routes.public.dcx_api_routes_public_build_time_ux_strings_bundle import (
    dcx_api_routes_public_build_time_ux_strings_bundle_router,
)
from routes.public.dcx_api_routes_public_build_time_content_pages_bundle import (
    dcx_api_routes_public_build_time_content_pages_bundle_router,
)
from routes.public.dcx_api_routes_public_reference_countries_bundle import (
    dcx_api_routes_public_reference_countries_bundle_router,
)
from routes.public.dcx_api_routes_public_emails_send_link_redirect import (
    dcx_api_routes_public_emails_send_link_redirect_router,
)
from routes.public.dcx_api_routes_public_email_preferences_unsubscribe import (
    dcx_api_routes_public_email_preferences_unsubscribe_router,
)
from routes.public.dcx_api_routes_public_meta_whatsapp_webhooks import (
    dcx_api_routes_public_meta_whatsapp_webhooks_router,
)
from routes.public.dcx_api_routes_public_resend_webhooks import (
    dcx_api_routes_public_resend_webhooks_router,
)
from routes.auth.dcx_api_routes_auth_login_password import (
    dcx_api_routes_auth_login_password_router,
)
from routes.auth.dcx_api_routes_auth_app_ux_strings_bundle import (
    dcx_api_routes_auth_app_ux_strings_bundle_router,
)
from routes.auth.dcx_api_routes_auth_logout import (
    dcx_api_routes_auth_logout_router,
)
from routes.auth.dcx_api_routes_auth_password_complete_set import (
    dcx_api_routes_auth_password_complete_set_router,
)
from routes.auth.dcx_api_routes_auth_password_request_reset import (
    dcx_api_routes_auth_password_request_reset_router,
)
from routes.auth.dcx_api_routes_auth_session import (
    dcx_api_routes_auth_session_router,
)
from routes.admin.dcx_api_routes_admin_users_list import (
    dcx_api_routes_admin_users_list_router,
)
from routes.admin.dcx_api_routes_admin_user_detail import (
    dcx_api_routes_admin_user_detail_router,
)
from routes.admin.dcx_api_routes_admin_content_ux_strings_catalog import (
    dcx_api_routes_admin_content_ux_strings_catalog_router,
)
from routes.admin.dcx_api_routes_admin_content_ux_string_create_translation import (
    dcx_api_routes_admin_content_ux_string_create_translation_router,
)
from routes.admin.dcx_api_routes_admin_content_ux_strings_save_live_row import (
    dcx_api_routes_admin_content_ux_strings_save_live_row_router,
)
from routes.admin.dcx_api_routes_admin_content_emails_catalog import (
    dcx_api_routes_admin_content_emails_catalog_router,
)
from routes.admin.dcx_api_routes_admin_content_email_create_translation import (
    dcx_api_routes_admin_content_email_create_translation_router,
)
from routes.admin.dcx_api_routes_admin_content_sequence_email_create_draft import (
    dcx_api_routes_admin_content_sequence_email_create_draft_router,
)
from routes.admin.dcx_api_routes_admin_content_emails_save_live_row import (
    dcx_api_routes_admin_content_emails_save_live_row_router,
)
from routes.admin.dcx_api_routes_admin_content_page_categories_catalog import (
    dcx_api_routes_admin_content_page_categories_catalog_router,
)
from routes.admin.dcx_api_routes_admin_content_page_category_detail import (
    dcx_api_routes_admin_content_page_category_detail_router,
)
from routes.admin.dcx_api_routes_admin_content_page_category_create_draft import (
    dcx_api_routes_admin_content_page_category_create_draft_router,
)
from routes.admin.dcx_api_routes_admin_content_page_category_create_translation import (
    dcx_api_routes_admin_content_page_category_create_translation_router,
)
from routes.admin.dcx_api_routes_admin_content_page_category_save_live_row import (
    dcx_api_routes_admin_content_page_category_save_live_row_router,
)
from routes.admin.dcx_api_routes_admin_content_pages_catalog import (
    dcx_api_routes_admin_content_pages_catalog_router,
)
from routes.admin.dcx_api_routes_admin_content_page_detail import (
    dcx_api_routes_admin_content_page_detail_router,
)
from routes.admin.dcx_api_routes_admin_content_page_create_draft import (
    dcx_api_routes_admin_content_page_create_draft_router,
)
from routes.admin.dcx_api_routes_admin_content_page_create_translation import (
    dcx_api_routes_admin_content_page_create_translation_router,
)
from routes.admin.dcx_api_routes_admin_content_page_save_live_row import (
    dcx_api_routes_admin_content_page_save_live_row_router,
)
from routes.admin.dcx_api_routes_admin_content_page_publish_live_row import (
    dcx_api_routes_admin_content_page_publish_live_row_router,
)
from routes.admin.dcx_api_routes_admin_content_page_archive_live_row import (
    dcx_api_routes_admin_content_page_archive_live_row_router,
)
from routes.admin.dcx_api_routes_admin_content_newsletters_catalog import (
    dcx_api_routes_admin_content_newsletters_catalog_router,
)
from routes.admin.dcx_api_routes_admin_content_newsletter_detail import (
    dcx_api_routes_admin_content_newsletter_detail_router,
)
from routes.admin.dcx_api_routes_admin_content_newsletter_create_draft import (
    dcx_api_routes_admin_content_newsletter_create_draft_router,
)
from routes.admin.dcx_api_routes_admin_content_newsletter_create_translation import (
    dcx_api_routes_admin_content_newsletter_create_translation_router,
)
from routes.admin.dcx_api_routes_admin_content_newsletter_sends_catalog import (
    dcx_api_routes_admin_content_newsletter_sends_catalog_router,
)
from routes.admin.dcx_api_routes_admin_content_newsletter_send_prepare import (
    dcx_api_routes_admin_content_newsletter_send_prepare_router,
)
from routes.admin.dcx_api_routes_admin_content_newsletter_send_cancel import (
    dcx_api_routes_admin_content_newsletter_send_cancel_router,
)
from routes.admin.dcx_api_routes_admin_content_newsletter_send_recipients import (
    dcx_api_routes_admin_content_newsletter_send_recipients_router,
)
from routes.admin.dcx_api_routes_admin_content_email_sequences_catalog import (
    dcx_api_routes_admin_content_email_sequences_catalog_router,
)
from routes.admin.dcx_api_routes_admin_content_email_sequence_create_draft import (
    dcx_api_routes_admin_content_email_sequence_create_draft_router,
)
from routes.admin.dcx_api_routes_admin_content_email_sequence_detail import (
    dcx_api_routes_admin_content_email_sequence_detail_router,
)
from routes.admin.dcx_api_routes_admin_content_email_sequence_save import (
    dcx_api_routes_admin_content_email_sequence_save_router,
)
from routes.admin.dcx_api_routes_admin_schedule_operations_catalog import (
    dcx_api_routes_admin_schedule_operations_catalog_router,
)
from routes.admin.dcx_api_routes_admin_jobs_email_cron_run import (
    dcx_api_routes_admin_jobs_email_cron_run_router,
)
from routes.admin.dcx_api_routes_admin_public_site_publish_status import (
    dcx_api_routes_admin_public_site_publish_status_router,
)
from routes.admin.dcx_api_routes_admin_public_site_publish_run import (
    dcx_api_routes_admin_public_site_publish_run_router,
)
from routes.admin.dcx_api_routes_admin_public_site_mark_local_rebuild_complete import (
    dcx_api_routes_admin_public_site_mark_local_rebuild_complete_router,
)
from routes.users.dcx_api_routes_users_me_account_summary import (
    dcx_api_routes_users_me_account_summary_router,
)
from routes.users.dcx_api_routes_users_me_activity import (
    dcx_api_routes_users_me_activity_router,
)
from routes.users.dcx_api_routes_users_me_usage import (
    dcx_api_routes_users_me_usage_router,
)
from routes.users.dcx_api_routes_users_me_account_settings import (
    dcx_api_routes_users_me_account_settings_router,
)
from routes.users.dcx_api_routes_users_me_account_phone_request_whatsapp_verification_link import (
    dcx_api_routes_users_me_account_phone_request_whatsapp_verification_link_router,
)
from routes.users.dcx_api_routes_users_me_account_phone_set_primary import (
    dcx_api_routes_users_me_account_phone_set_primary_router,
)
from routes.users.dcx_api_routes_users_me_messages_create import (
    dcx_api_routes_users_me_messages_create_router,
)
from routes.users.dcx_api_routes_users_me_messages_detail import (
    dcx_api_routes_users_me_messages_detail_router,
)
from routes.users.dcx_api_routes_users_me_messages_retry_analysis import (
    dcx_api_routes_users_me_messages_retry_analysis_router,
)
from routes.users.dcx_api_routes_users_me_messages_inbox import (
    dcx_api_routes_users_me_messages_inbox_router,
)
from routes.users.dcx_api_routes_users_me_trades_catalog import (
    dcx_api_routes_users_me_trades_catalog_router,
)
from routes.users.dcx_api_routes_users_me_trade_detail import (
    dcx_api_routes_users_me_trade_detail_router,
)
from routes.users.dcx_api_routes_users_me_trade_confirm import (
    dcx_api_routes_users_me_trade_confirm_router,
)
from routes.users.dcx_api_routes_users_me_trade_reject import (
    dcx_api_routes_users_me_trade_reject_router,
)
from routes.users.dcx_api_routes_users_me_trade_update import (
    dcx_api_routes_users_me_trade_update_router,
)
from routes.users.dcx_api_routes_users_me_trade_visibility import (
    dcx_api_routes_users_me_trade_visibility_router,
)
from routes.users.dcx_api_routes_users_me_market_topics_catalog import (
    dcx_api_routes_users_me_market_topics_catalog_router,
)
from routes.users.dcx_api_routes_users_me_market_topic_detail import (
    dcx_api_routes_users_me_market_topic_detail_router,
)
from routes.users.dcx_api_routes_users_me_market_topic_visibility import (
    dcx_api_routes_users_me_market_topic_visibility_router,
)
from routes.users.dcx_api_routes_users_me_market_trades import (
    dcx_api_routes_users_me_market_trades_router,
)
from routes.users.dcx_api_routes_users_me_trade_threads import (
    dcx_api_routes_users_me_trade_threads_router,
)
from routes.users.dcx_api_routes_users_me_market_forum import (
    dcx_api_routes_users_me_market_forum_router,
)
from routes.users.dcx_api_routes_users_me_message_attachment_file import (
    dcx_api_routes_users_me_message_attachment_file_router,
)
from routes.users.dcx_api_routes_users_me_file_object import (
    dcx_api_routes_users_me_file_object_router,
)
from routes.users.dcx_api_routes_users_account_phone_verify_whatsapp_link import (
    dcx_api_routes_users_account_phone_verify_whatsapp_link_router,
)
from routes.users.dcx_api_routes_users_signup_email import (
    dcx_api_routes_users_signup_email_router,
)
from routes.users.dcx_api_routes_users_signup_email_resend_otp import (
    dcx_api_routes_users_signup_email_resend_otp_router,
)
from routes.users.dcx_api_routes_users_signup_email_verify_otp import (
    dcx_api_routes_users_signup_email_verify_otp_router,
)
from routes.users.dcx_api_routes_users_support import read_allowed_dcx_frontend_origins

logger = logging.getLogger("uvicorn.error")
DCX_API_STATIC_DIR = Path(__file__).resolve().parent / "static"


app = FastAPI(
    title="DCX API Bootstrap",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(read_allowed_dcx_frontend_origins()),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Origin"],
)
app.mount("/static", StaticFiles(directory=DCX_API_STATIC_DIR), name="static")

app.include_router(dcx_api_routes_auth_login_password_router)
app.include_router(dcx_api_routes_auth_app_ux_strings_bundle_router)
app.include_router(dcx_api_routes_auth_logout_router)
app.include_router(dcx_api_routes_auth_password_complete_set_router)
app.include_router(dcx_api_routes_auth_password_request_reset_router)
app.include_router(dcx_api_routes_auth_session_router)
app.include_router(dcx_api_routes_admin_users_list_router)
app.include_router(dcx_api_routes_admin_user_detail_router)
app.include_router(dcx_api_routes_admin_content_ux_strings_catalog_router)
app.include_router(dcx_api_routes_admin_content_ux_string_create_translation_router)
app.include_router(dcx_api_routes_admin_content_ux_strings_save_live_row_router)
app.include_router(dcx_api_routes_admin_content_emails_catalog_router)
app.include_router(dcx_api_routes_admin_content_email_create_translation_router)
app.include_router(dcx_api_routes_admin_content_sequence_email_create_draft_router)
app.include_router(dcx_api_routes_admin_content_emails_save_live_row_router)
app.include_router(dcx_api_routes_admin_content_page_categories_catalog_router)
app.include_router(dcx_api_routes_admin_content_page_category_detail_router)
app.include_router(dcx_api_routes_admin_content_page_category_create_draft_router)
app.include_router(dcx_api_routes_admin_content_page_category_create_translation_router)
app.include_router(dcx_api_routes_admin_content_page_category_save_live_row_router)
app.include_router(dcx_api_routes_admin_content_pages_catalog_router)
app.include_router(dcx_api_routes_admin_content_page_detail_router)
app.include_router(dcx_api_routes_admin_content_page_create_draft_router)
app.include_router(dcx_api_routes_admin_content_page_create_translation_router)
app.include_router(dcx_api_routes_admin_content_page_save_live_row_router)
app.include_router(dcx_api_routes_admin_content_page_publish_live_row_router)
app.include_router(dcx_api_routes_admin_content_page_archive_live_row_router)
app.include_router(dcx_api_routes_admin_content_newsletters_catalog_router)
app.include_router(dcx_api_routes_admin_content_newsletter_detail_router)
app.include_router(dcx_api_routes_admin_content_newsletter_create_draft_router)
app.include_router(dcx_api_routes_admin_content_newsletter_create_translation_router)
app.include_router(dcx_api_routes_admin_content_newsletter_sends_catalog_router)
app.include_router(dcx_api_routes_admin_content_newsletter_send_prepare_router)
app.include_router(dcx_api_routes_admin_content_newsletter_send_cancel_router)
app.include_router(dcx_api_routes_admin_content_newsletter_send_recipients_router)
app.include_router(dcx_api_routes_admin_content_email_sequences_catalog_router)
app.include_router(dcx_api_routes_admin_content_email_sequence_create_draft_router)
app.include_router(dcx_api_routes_admin_content_email_sequence_detail_router)
app.include_router(dcx_api_routes_admin_content_email_sequence_save_router)
app.include_router(dcx_api_routes_admin_schedule_operations_catalog_router)
app.include_router(dcx_api_routes_admin_jobs_email_cron_run_router)
app.include_router(dcx_api_routes_admin_public_site_publish_status_router)
app.include_router(dcx_api_routes_admin_public_site_publish_run_router)
app.include_router(dcx_api_routes_admin_public_site_mark_local_rebuild_complete_router)
app.include_router(dcx_api_routes_users_me_account_summary_router)
app.include_router(dcx_api_routes_users_me_activity_router)
app.include_router(dcx_api_routes_users_me_usage_router)
app.include_router(dcx_api_routes_users_me_account_settings_router)
app.include_router(dcx_api_routes_users_me_account_phone_request_whatsapp_verification_link_router)
app.include_router(dcx_api_routes_users_me_account_phone_set_primary_router)
app.include_router(dcx_api_routes_users_me_messages_inbox_router)
app.include_router(dcx_api_routes_users_me_messages_detail_router)
app.include_router(dcx_api_routes_users_me_messages_create_router)
app.include_router(dcx_api_routes_users_me_messages_retry_analysis_router)
app.include_router(dcx_api_routes_users_me_trades_catalog_router)
app.include_router(dcx_api_routes_users_me_trade_detail_router)
app.include_router(dcx_api_routes_users_me_trade_confirm_router)
app.include_router(dcx_api_routes_users_me_trade_reject_router)
app.include_router(dcx_api_routes_users_me_trade_update_router)
app.include_router(dcx_api_routes_users_me_trade_visibility_router)
app.include_router(dcx_api_routes_users_me_market_topics_catalog_router)
app.include_router(dcx_api_routes_users_me_market_topic_detail_router)
app.include_router(dcx_api_routes_users_me_market_topic_visibility_router)
app.include_router(dcx_api_routes_users_me_market_trades_router)
app.include_router(dcx_api_routes_users_me_trade_threads_router)
app.include_router(dcx_api_routes_users_me_market_forum_router)
app.include_router(dcx_api_routes_users_me_file_object_router)
app.include_router(dcx_api_routes_users_me_message_attachment_file_router)
app.include_router(dcx_api_routes_users_account_phone_verify_whatsapp_link_router)
app.include_router(dcx_api_routes_users_signup_email_router)
app.include_router(dcx_api_routes_users_signup_email_verify_otp_router)
app.include_router(dcx_api_routes_users_signup_email_resend_otp_router)
app.include_router(dcx_api_routes_public_build_time_api_test_router)
app.include_router(dcx_api_routes_public_build_time_ux_strings_bundle_router)
app.include_router(dcx_api_routes_public_build_time_content_pages_bundle_router)
app.include_router(dcx_api_routes_public_reference_countries_bundle_router)
app.include_router(dcx_api_routes_public_emails_send_link_redirect_router)
app.include_router(dcx_api_routes_public_email_preferences_unsubscribe_router)
app.include_router(dcx_api_routes_public_meta_whatsapp_webhooks_router)
app.include_router(dcx_api_routes_public_resend_webhooks_router)
app.include_router(dcx_api_routes_files_r2_hello_world_router)


@app.get("/", response_class=HTMLResponse)
def get_dcx_api_root_welcome_response() -> str:
    """
    CONTRACT:
      preconditions:
        - The FastAPI application is running and able to receive HTTP requests from local frontend origins.
        - The configured Postgres database is reachable for one read-only bootstrap query.
      postconditions:
        - Returns one minimal branded HTML placeholder page for the API hostname.
        - Does not expose route hints, backend capability names, or other attacker-oriented discovery detail.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why: This exists to keep the backend base URL visually quiet and branded without exposing any useful route hints to attackers or curious crawlers.
      when_to_use:
        - During local smoke testing of the backend hostname.
        - During initial deployment verification of the API service shell.
      when_not_to_use:
        - Do not use this as the long-term health or readiness contract once real service checks exist.
        - Do not use this route to expose sample database data.
      what_can_go_wrong:
        - The service may fail to start because dependencies are missing.
        - The route may fail if the ASGI app is imported from the wrong module path.
        - Browser calls from hosted public shells may fail if CORS does not allow the current public origins.
      what_comes_next:
        - Add dedicated private readiness routes when deployment needs them.
        - Keep the public API hostname visually quiet while browser consumers use explicit route contracts.

    TESTS:
      - root_route_returns_minimal_placeholder_html
      - root_route_allows_local_frontend_origin
      - root_route_allows_local_app_origin
      - root_route_allows_local_admin_origin

    ERRORS:
      - API_HELLO_WORLD_IMPORT_FAILURE:
          suggested_action: Confirm FastAPI and uvicorn are installed and the server is launched from the dcx_api repo root.
          common_causes:
            - requirements were not installed
            - uvicorn target module path is wrong
          recovery_steps:
            - Run pip install -r requirements.txt in the intended environment.
            - Start the server with uvicorn dcx_api_app:app --reload.
          retry_safe: true
      - API_SHARED_WELCOME_CORS_MISCONFIGURED:
          suggested_action: Confirm the public email-signup CORS allowlist still matches the intended public origins.
          common_causes:
            - CORS allowlist too narrow
            - public hostnames changed
            - middleware configuration edited without updating tests
          recovery_steps:
            - Re-check the allow_origins list in dcx_api_app.py.
            - Confirm the frontend is deployed on the expected hostname.
            - Retry after redeploying the backend.
          retry_safe: true

    CODE:
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>DCX API | Service Root</title>
    <style>
      :root {
        color-scheme: light;
        font-family: Arial, sans-serif;
      }
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: linear-gradient(180deg, #f4f7fb 0%, #ffffff 100%);
        color: #0e1830;
      }
      .dcx_api_placeholder_shell {
        display: grid;
        place-items: center;
        width: min(180px, 42vw);
        aspect-ratio: 1;
      }
      .dcx_api_placeholder_logo {
        width: 100%;
        height: auto;
        display: block;
      }
    </style>
  </head>
  <body>
    <main class="dcx_api_placeholder_shell">
      <img
        class="dcx_api_placeholder_logo"
        src="/static/dcx_logo.png"
        alt="DCX"
      />
    </main>
  </body>
</html>"""
