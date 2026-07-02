"""
CONTEXT:
This file owns the DCX app-facing `/users/me/usage` HTTP boundary.
It exists so users can see their basic MVP token account without exposing billing assumptions.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from usage.read_dcx_user_usage_summary import read_dcx_user_usage_summary

dcx_api_routes_users_me_usage_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_usage_router.get("/me/usage", response_model=None)
def get_authenticated_dcx_user_usage(request: Request):
    return _read_authenticated_dcx_user_usage_response(request=request, days=30)


@dcx_api_routes_users_me_usage_router.get("/me/usage/days/{days}", response_model=None)
def get_authenticated_dcx_user_usage_for_days(request: Request, days: int):
    return _read_authenticated_dcx_user_usage_response(request=request, days=days)


def _read_authenticated_dcx_user_usage_response(request: Request, days: int):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session cookie is present.
      postconditions:
        - Returns canonical usage totals and recent LLM usage events for the current user.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - MVP users need a simple token usage account now, before full spend controls.
      WHEN TO USE it:
        - Use it from the app Usage screen.
      WHEN NOT TO USE it:
        - Do not use it as an invoice or commercial billing statement.
      WHAT CAN GO WRONG:
        - No session is present or usage tables have not been migrated.
      WHAT COMES NEXT:
        - Add budgets and cost conversion after usage patterns are known.

    TESTS:
      - compile smoke; route integration tests can be added after the migration is in the test DB.

    ERRORS:
      - API_DCX_AUTH_SESSION_REQUIRED:
          suggested_action: Sign in and retry.
          common_causes:
            - no authenticated session
          recovery_steps:
            - Sign in again.
          retry_safe: true
      - API_DCX_USER_USAGE_READ_FAILED:
          suggested_action: Apply migrations and retry after backend/database health is restored.
          common_causes:
            - missing usage table
            - database unavailable
          recovery_steps:
            - Run migrations.
            - Retry.
          retry_safe: true

    CODE:
    """
    authenticated_user_id, identity_resolution_mode, error_response = read_authenticated_dcx_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    normalized_days = max(1, min(int(days or 30), 365))
    try:
        usage_summary = read_dcx_user_usage_summary(
            user_id=authenticated_user_id,
            daily_window_days=normalized_days,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_USER_USAGE_READ_FAILED",
                    "message": "We could not load DCX usage just now.",
                    "suggested_action": "Retry after backend/database health is restored.",
                },
            },
        )

    return {
        "ok": True,
        "data": usage_summary,
        "context": {
            "surface": "app",
            "view": "usage",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
