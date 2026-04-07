"""
CONTEXT:
This file owns the first DCX app-facing `/users/me/account-settings` HTTP boundary.
It exists so the user app can autosave a small set of low-risk account fields from one
stable backend contract before real auth and more complex verification flows are added.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from fastapi.responses import JSONResponse

from routes.users.dcx_api_routes_users_support import (
    read_permitted_local_debug_user_id_or_error_response,
)
from users.account.read_authenticated_dcx_user_account_summary import (
    read_authenticated_dcx_user_account_summary_capability,
)
from users.account.save_authenticated_dcx_user_account_editable_settings import (
    save_authenticated_dcx_user_account_editable_settings_capability,
)

dcx_api_routes_users_me_account_settings_router = APIRouter(prefix="/users", tags=["users"])


class DcxUsersMeAccountSettingsSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_language_id: int | None
    preferred_timezone_id: int | None
    email_communication_preference: str


@dcx_api_routes_users_me_account_settings_router.post("/me/account-settings", response_model=None)
def post_authenticated_dcx_user_account_settings(
    account_settings_save_request: DcxUsersMeAccountSettingsSaveRequest,
    user_id: int | None = Query(default=None, ge=1),
):
    """
    CONTRACT:
      preconditions:
        - Real auth is not wired yet, so local development may temporarily supply one `user_id`
          query parameter for account-page testing.
        - The body contains only the currently editable account fields.
      postconditions:
        - Saves the requested account settings for the current user.
        - Returns a canonical success wrapper containing the refreshed account-summary payload.
      side_effects:
        - updates mutable settings in `stephen_dcx_users`
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first editable app account surface needs one precise save door with autosave-friendly
          semantics before higher-risk changes such as email verification are added.
      WHEN TO USE it:
        - Use it from the app account page for preferred language and communication-preference saves.
      WHEN NOT TO USE it:
        - Do not use it for primary-email changes or admin-side user edits.
      WHAT CAN GO WRONG:
        - No authenticated identity is available yet.
        - The user id can be stale.
        - The selected language or preference can be invalid.
        - Database access can fail.
      WHAT COMES NEXT:
        - Keep this route stable while auth becomes real and more settings become editable.

    TESTS:
      - test_users_me_account_settings_route_saves_and_returns_refreshed_account_payload_for_local_debug_user_id
      - test_users_me_account_settings_route_returns_auth_required_without_debug_identity

    ERRORS:
      - API_USERS_ME_AUTH_REQUIRED:
          suggested_action: Sign in once auth is connected, or use `?user_id=` locally while the
            account page is still in the temporary bootstrap phase.
          common_causes:
            - no authenticated session yet
            - no local debug user id supplied
          recovery_steps:
            - Add `?user_id=<existing_user_id>` during local development.
          retry_safe: true
      - API_USERS_ME_ACCOUNT_SETTINGS_INVALID:
          suggested_action: Refresh the page options and retry with a supported value.
          common_causes:
            - invalid language id
            - invalid communication preference
          recovery_steps:
            - Refresh the page.
            - Retry with a supported value.
          retry_safe: true

    CODE:
    """
    authenticated_user_id, error_response = read_permitted_local_debug_user_id_or_error_response(user_id)
    if error_response is not None:
        return error_response

    try:
        save_authenticated_dcx_user_account_editable_settings_capability(
            authenticated_user_id=authenticated_user_id,
            preferred_language_id=account_settings_save_request.preferred_language_id,
            preferred_timezone_id=account_settings_save_request.preferred_timezone_id,
            email_communication_preference=account_settings_save_request.email_communication_preference,
        )
        refreshed_account_summary = read_authenticated_dcx_user_account_summary_capability(
            authenticated_user_id=authenticated_user_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)

        if error_code == "API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_SETTINGS_NOT_FOUND",
                        "message": "We could not find that DCX user account.",
                        "suggested_action": "Retry with a valid local debug user id.",
                    },
                },
            )

        if error_code in {
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_LANGUAGE_INVALID",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_TIMEZONE_INVALID",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_EMAIL_PREFERENCE_INVALID",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_ACCOUNT_SETTINGS_INVALID",
                        "message": "We could not save those account settings.",
                        "suggested_action": "Refresh the available options and retry with a supported value.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_ACCOUNT_SETTINGS_SAVE_FAILED",
                    "message": "We could not save the DCX account settings just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": refreshed_account_summary,
        "context": {
            "surface": "app",
            "view": "account_summary",
            "operation": "account_settings_saved",
            "identity_resolution_mode": "temporary_user_id_query_parameter",
        },
    }
