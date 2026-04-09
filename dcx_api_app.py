"""
CONTEXT:
This file is the composition root for the DCX API workspace.
It exists to assemble middleware, startup schema application, a quiet branded root route, and the
dedicated route modules while keeping HTTP route bodies out of the app root.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from storage.dcx_apply_initial_user_signup_schema_to_configured_database import (
    apply_initial_user_signup_schema_to_configured_database,
)
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
from routes.admin.dcx_api_routes_admin_content_ux_strings_catalog import (
    dcx_api_routes_admin_content_ux_strings_catalog_router,
)
from routes.admin.dcx_api_routes_admin_content_ux_strings_save_live_row import (
    dcx_api_routes_admin_content_ux_strings_save_live_row_router,
)
from routes.admin.dcx_api_routes_admin_content_emails_catalog import (
    dcx_api_routes_admin_content_emails_catalog_router,
)
from routes.admin.dcx_api_routes_admin_content_emails_save_live_row import (
    dcx_api_routes_admin_content_emails_save_live_row_router,
)
from routes.admin.dcx_api_routes_admin_content_page_categories_catalog import (
    dcx_api_routes_admin_content_page_categories_catalog_router,
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
from routes.users.dcx_api_routes_users_me_account_settings import (
    dcx_api_routes_users_me_account_settings_router,
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


@asynccontextmanager
async def dcx_api_application_lifespan(application: FastAPI):
    """
    CONTRACT:
      preconditions:
        - The FastAPI application is starting in a process that should have database access.
        - The initial user schema capability is importable from the backend workspace.
      postconditions:
        - The hardened DCX user-signup schema has been ensured before request handling begins.
        - No seed rows were inserted and no existing rows were deleted.
      side_effects:
        - executes idempotent database schema initialization during application startup
      idempotent: true
      retry_safe: true
      async: true
      idempotency_key: dcx_api_startup_apply_initial_user_schema_v1
      locks: []
      contention_strategy: rely on the underlying schema capability to keep repeated startup applies safe

    NARRATIVE:
      why:
        - This exists so a fresh local or Render database automatically gets the first durable user schema without a separate manual setup step.
        - The first real user milestone should start from an initialized schema, not from remembered manual SQL paste steps.
      when_to_use:
        - At normal API process startup locally and in production.
      when_not_to_use:
        - Do not use this lifespan hook to seed demo data.
        - Do not grow this into a catch-all migration engine once explicit migrations exist.
      what_can_go_wrong:
        - Startup will fail if the configured database is unreachable.
        - Startup will fail if the database user lacks schema-write permissions.
      what_comes_next:
        - Add the first users and auth challenge capabilities on top of the initialized schema.
        - Later replace startup-only schema evolution with explicit non-breaking migrations where needed.

    TESTS:
      - covered_indirectly_by_schema_apply_capability_tests
      - startup_path_ensures_tables_before_new_user_flow_capabilities_are_added

    ERRORS:
      - API_INITIAL_USER_SCHEMA_APPLY_FAILED:
          suggested_action: Confirm database connectivity and schema-write permissions for the configured backend database.
          common_causes:
            - Render or local Postgres unavailable
            - wrong db env configuration
            - SQL file missing
          recovery_steps:
            - Re-check db_config values.
            - Confirm the SQL file still exists in storage.
            - Retry backend startup after restoring database access.
          retry_safe: true
          what_changed: none if startup failed before the SQL transaction committed
          rollback_needed: false
          rollback_operation: inspect manually only if a partial external schema change occurred

    CODE:
    """
    apply_initial_user_signup_schema_to_configured_database()
    yield


app = FastAPI(
    title="DCX API Bootstrap",
    version="0.0.1",
    lifespan=dcx_api_application_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(read_allowed_dcx_frontend_origins()),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
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
app.include_router(dcx_api_routes_admin_content_ux_strings_catalog_router)
app.include_router(dcx_api_routes_admin_content_ux_strings_save_live_row_router)
app.include_router(dcx_api_routes_admin_content_emails_catalog_router)
app.include_router(dcx_api_routes_admin_content_emails_save_live_row_router)
app.include_router(dcx_api_routes_admin_content_page_categories_catalog_router)
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
app.include_router(dcx_api_routes_admin_public_site_publish_status_router)
app.include_router(dcx_api_routes_admin_public_site_publish_run_router)
app.include_router(dcx_api_routes_admin_public_site_mark_local_rebuild_complete_router)
app.include_router(dcx_api_routes_users_me_account_summary_router)
app.include_router(dcx_api_routes_users_me_account_settings_router)
app.include_router(dcx_api_routes_users_signup_email_router)
app.include_router(dcx_api_routes_users_signup_email_verify_otp_router)
app.include_router(dcx_api_routes_users_signup_email_resend_otp_router)
app.include_router(dcx_api_routes_public_build_time_api_test_router)
app.include_router(dcx_api_routes_public_build_time_ux_strings_bundle_router)
app.include_router(dcx_api_routes_public_build_time_content_pages_bundle_router)
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
    <title>DCX API</title>
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
