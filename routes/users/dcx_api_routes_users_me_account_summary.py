"""
CONTEXT:
This file owns the first DCX app-facing `/users/me/account-summary` HTTP boundary.
It exists so the user app can render a compact authenticated account screen from one
stable backend contract behind the shared session-cookie auth system.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from users.account.read_authenticated_dcx_user_account_summary import (
    read_authenticated_dcx_user_account_summary_capability,
)

dcx_api_routes_users_me_account_summary_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_account_summary_router.get("/me/account-summary", response_model=None)
def get_authenticated_dcx_user_account_summary(
    request: Request,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session cookie is present.
      postconditions:
        - Returns a canonical success wrapper containing one account-summary payload for the
          current user once an identity is resolved.
        - Returns a canonical error wrapper when no authenticated app session is available.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first `app.dcxagent.ai/me/account` screen needs a stable authenticated read contract.
      WHEN TO USE it:
        - Use it from the user app account page.
      WHEN NOT TO USE it:
        - Do not use it for admin lists or as a direct password-auth boundary.
      WHAT CAN GO WRONG:
        - No authenticated app session is available.
        - Database access can fail.
      WHAT COMES NEXT:
        - Keep the route stable while more protected app surfaces reuse the same session identity.

    TESTS:
      - test_users_me_account_summary_route_returns_account_payload_for_authenticated_session
      - test_users_me_account_summary_route_returns_auth_required_without_authenticated_session

    ERRORS:
      - API_DCX_AUTH_SESSION_REQUIRED:
          suggested_action: Sign in through the DCX app login flow, then retry.
          common_causes:
            - no authenticated session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the app login screen.
          retry_safe: true
      - API_USERS_ME_ACCOUNT_SUMMARY_NOT_FOUND:
          suggested_action: Recreate the user through signup or inspect the backing account row.
          common_causes:
            - deleted user row
          recovery_steps:
            - Recreate the user if needed.
          retry_safe: true

    CODE:
    """
    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(
            request=request,
        )
    )
    if error_response is not None:
        return error_response

    try:
        account_summary = read_authenticated_dcx_user_account_summary_capability(
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
                        "code": "API_USERS_ME_ACCOUNT_SUMMARY_NOT_FOUND",
                        "message": "We could not find that DCX user account.",
                        "suggested_action": "Recreate the user through signup or inspect the backing account row.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_ACCOUNT_SUMMARY_READ_FAILED",
                    "message": "We could not load the DCX account summary just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": account_summary,
        "context": {
            "surface": "app",
            "view": "account_summary",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
