"""
CONTEXT:
This file owns the first DCX app-facing `/users/me/account-settings` HTTP boundary.
It exists so the user app can autosave a small set of low-risk account fields from one
stable authenticated backend contract while more complex verification flows are added.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from fastapi.responses import JSONResponse

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
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
    public_display_name: str
    public_handle: str
    public_identity_mode: str
    default_interaction_channel: str
    network_dm_acceptance_mode: str = "everyone"
    network_profile_image_url: str = ""
    trade_interest_material_keys: list[str] = []
    sidebar_clock_timezone_ids: list[int] = []
    selected_language_ids: list[int] | None = None
    selected_timezone_ids: list[int] | None = None
    selected_country_ids: list[int] | None = None


@dcx_api_routes_users_me_account_settings_router.post("/me/account-settings", response_model=None)
def post_authenticated_dcx_user_account_settings(
    request: Request,
    account_settings_save_request: DcxUsersMeAccountSettingsSaveRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session cookie is present.
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
        - No authenticated identity is available.
        - The selected language or preference can be invalid.
        - Database access can fail.
      WHAT COMES NEXT:
        - Keep this route stable while auth becomes real and more settings become editable.

    TESTS:
      - test_users_me_account_settings_route_saves_and_returns_refreshed_account_payload_for_authenticated_session
      - test_users_me_account_settings_route_returns_auth_required_without_authenticated_session

    ERRORS:
      - API_DCX_AUTH_SESSION_REQUIRED:
          suggested_action: Sign in through the DCX app login flow, then retry.
          common_causes:
            - no authenticated session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the app login screen.
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
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(
            request=request,
        )
    )
    if error_response is not None:
        return error_response

    try:
        save_authenticated_dcx_user_account_editable_settings_capability(
            authenticated_user_id=authenticated_user_id,
            preferred_language_id=account_settings_save_request.preferred_language_id,
            preferred_timezone_id=account_settings_save_request.preferred_timezone_id,
            email_communication_preference=account_settings_save_request.email_communication_preference,
            public_display_name=account_settings_save_request.public_display_name,
            public_handle=account_settings_save_request.public_handle,
            public_identity_mode=account_settings_save_request.public_identity_mode,
            default_interaction_channel=account_settings_save_request.default_interaction_channel,
            network_dm_acceptance_mode=account_settings_save_request.network_dm_acceptance_mode,
            network_profile_image_url=account_settings_save_request.network_profile_image_url,
            trade_interest_material_keys=account_settings_save_request.trade_interest_material_keys,
            sidebar_clock_timezone_ids=account_settings_save_request.sidebar_clock_timezone_ids,
            selected_language_ids=account_settings_save_request.selected_language_ids,
            selected_timezone_ids=account_settings_save_request.selected_timezone_ids,
            selected_country_ids=account_settings_save_request.selected_country_ids,
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
                        "suggested_action": "Recreate the user through signup or inspect the backing account row.",
                    },
                },
            )

        if error_code in {
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_LANGUAGE_INVALID",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_TIMEZONE_INVALID",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_EMAIL_PREFERENCE_INVALID",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_PUBLIC_IDENTITY_INVALID",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_PUBLIC_HANDLE_TAKEN",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_DEFAULT_INTERACTION_CHANNEL_INVALID",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_NETWORK_PROFILE_INVALID",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_TRADE_INTERESTS_INVALID",
            "API_AUTHENTICATED_DCX_USER_ACCOUNT_COUNTRY_INVALID",
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
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
