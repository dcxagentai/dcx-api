"""
CONTEXT:
This file is the composition root for the DCX API workspace.
It exists to assemble middleware, startup schema application, a minimal root route, and the
dedicated users router while keeping HTTP route bodies out of the app root.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from routes.auth.dcx_api_routes_auth_login_password import (
    dcx_api_routes_auth_login_password_router,
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

app.include_router(dcx_api_routes_auth_login_password_router)
app.include_router(dcx_api_routes_auth_logout_router)
app.include_router(dcx_api_routes_auth_password_complete_set_router)
app.include_router(dcx_api_routes_auth_password_request_reset_router)
app.include_router(dcx_api_routes_auth_session_router)
app.include_router(dcx_api_routes_admin_users_list_router)
app.include_router(dcx_api_routes_admin_content_ux_strings_catalog_router)
app.include_router(dcx_api_routes_admin_content_ux_strings_save_live_row_router)
app.include_router(dcx_api_routes_admin_content_emails_catalog_router)
app.include_router(dcx_api_routes_admin_content_emails_save_live_row_router)
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
app.include_router(dcx_api_routes_files_r2_hello_world_router)


@app.get("/")
def get_dcx_api_root_welcome_response() -> dict:
    """
    CONTRACT:
      preconditions:
        - The FastAPI application is running and able to receive HTTP requests from local frontend origins.
        - The configured Postgres database is reachable for one read-only bootstrap query.
      postconditions:
        - Returns a canonical success wrapper containing the backend welcome payload for the bootstrap shell.
        - Includes only minimal service metadata rather than public database proof data.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why: This exists to make the backend base URL itself useful as the first plumbing-proof route for local development and production on api.dcx.com.
      when_to_use:
        - During local smoke testing of the backend workspace.
        - During initial deployment verification of the API service shell.
      when_not_to_use:
        - Do not use this as the long-term health or readiness contract once real service checks exist.
        - Do not use this route to expose sample database data.
      what_can_go_wrong:
        - The service may fail to start because dependencies are missing.
        - The route may fail if the ASGI app is imported from the wrong module path.
        - Browser calls from hosted public shells may fail if CORS does not allow the current public origins.
      what_comes_next:
        - Add dedicated health/readiness routes.
        - Add the first real domain capabilities and project them through API routes.

    TESTS:
      - root_route_returns_ok_wrapper
      - root_route_returns_backend_identity
      - root_route_allows_local_frontend_origin
      - root_route_allows_public_pages_origin

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
    return {
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
                "Use /admin/users/list for the first dcx_admin users surface.",
                "Use /auth/login/password to create a shared app/admin browser session.",
                "Use /auth/session to check the current authenticated browser session.",
                "Use /auth/logout to revoke the current shared browser session.",
                "Use /auth/password/request-reset to start the email reset flow.",
                "Use /auth/password/complete-set to finish password setup or reset from the one-time token.",
                "Use /admin/content/ux-strings/catalog for the admin UX-strings viewer.",
                "Use /admin/content/ux-strings/save-live-row for immutable admin UX-string updates.",
                "Use /admin/content/emails/catalog for the admin emails viewer.",
                "Use /admin/content/emails/save-live-row for immutable admin email-template updates.",
                "Use the dedicated /users routes for public signup flow interactions.",
                "Use /users/me/account-summary for the first dcx_app account surface.",
                "Use /users/me/account-settings for the first dcx_app editable account save path.",
                "Add dedicated readiness and health routes when deployment needs them.",
            ],
            "related_operations": [
                "dcx_api_routes_admin_users_list_router",
                "dcx_api_routes_auth_login_password_router",
                "dcx_api_routes_auth_session_router",
                "dcx_api_routes_auth_logout_router",
                "dcx_api_routes_auth_password_request_reset_router",
                "dcx_api_routes_auth_password_complete_set_router",
                "dcx_api_routes_admin_content_ux_strings_catalog_router",
                "dcx_api_routes_admin_content_ux_strings_save_live_row_router",
                "dcx_api_routes_admin_content_emails_catalog_router",
                "dcx_api_routes_admin_content_emails_save_live_row_router",
                "dcx_api_routes_users_me_account_summary_router",
                "dcx_api_routes_users_me_account_settings_router",
                "dcx_api_routes_users_signup_email_router",
                "dcx_api_routes_users_signup_email_verify_otp_router",
                "dcx_api_routes_users_signup_email_resend_otp_router",
            ],
        },
    }
