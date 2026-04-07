"""
CONTEXT:
This file owns the first DCX app-facing `/users/me/account-summary` HTTP boundary.
It exists so the user app can render a compact authenticated account screen from one
stable backend contract before the broader app/admin auth system is fully in place.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from routes.users.dcx_api_routes_users_support import (
    read_permitted_local_debug_user_id_or_error_response,
)
from users.account.read_authenticated_dcx_user_account_summary import (
    read_authenticated_dcx_user_account_summary_capability,
)

dcx_api_routes_users_me_account_summary_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_account_summary_router.get("/me/account-summary", response_model=None)
def get_authenticated_dcx_user_account_summary(
    user_id: int | None = Query(default=None, ge=1),
):
    """
    CONTRACT:
      preconditions:
        - Real auth is not wired yet, so local development may temporarily supply one `user_id`
          query parameter for account-page testing.
      postconditions:
        - Returns a canonical success wrapper containing one account-summary payload for the
          current user once an identity is resolved.
        - Returns a canonical error wrapper when no current user identity is available yet.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first `app.dcxagent.ai/me/account` screen needs a real backend contract now, even
          though the durable auth/session system comes in the next phase.
      WHEN TO USE it:
        - Use it from the user app account page.
      WHEN NOT TO USE it:
        - Do not use it for admin lists or as the final auth boundary design.
      WHAT CAN GO WRONG:
        - No authenticated identity is available yet.
        - A stale local debug user id can point at no user row.
        - Database access can fail.
      WHAT COMES NEXT:
        - Replace the temporary local `user_id` query parameter path with real session/auth
          identity resolution while keeping the frontend route and payload stable.

    TESTS:
      - test_users_me_account_summary_route_returns_account_payload_for_local_debug_user_id
      - test_users_me_account_summary_route_returns_auth_required_without_debug_identity
      - test_users_me_account_summary_route_rejects_debug_user_id_outside_local_runtime

    ERRORS:
      - API_USERS_ME_AUTH_REQUIRED:
          suggested_action: Sign in once auth is connected, or use `?user_id=` locally while the
            account page is still in the temporary bootstrap phase.
          common_causes:
            - no authenticated session yet
            - no local debug user id supplied
          recovery_steps:
            - Add `?user_id=<existing_user_id>` during local development.
            - Later, sign in normally once auth is available.
          retry_safe: true
      - API_USERS_ME_ACCOUNT_SUMMARY_NOT_FOUND:
          suggested_action: Retry with a valid local debug user id or recreate the user through signup.
          common_causes:
            - stale user id
            - deleted user row
          recovery_steps:
            - Use a valid existing user id locally.
            - Recreate the user if needed.
          retry_safe: true

    CODE:
    """
    authenticated_user_id, error_response = read_permitted_local_debug_user_id_or_error_response(user_id)
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
                        "suggested_action": "Retry with a valid local debug user id.",
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
            "identity_resolution_mode": "temporary_user_id_query_parameter",
        },
    }
