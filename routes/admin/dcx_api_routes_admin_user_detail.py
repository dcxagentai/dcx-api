"""
CONTEXT:
This file owns the first admin-facing user detail HTTP boundary.
It exists so admins can inspect user usage and content-free activity without reading user messages.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)
from activity.read_dcx_user_activity_events import read_dcx_user_activity_events
from usage.read_dcx_user_usage_summary import read_dcx_user_usage_summary

dcx_api_routes_admin_user_detail_router = APIRouter(prefix="/admin", tags=["admin"])


@dcx_api_routes_admin_user_detail_router.get("/users/{user_id}/detail", response_model=None)
def get_dcx_admin_user_detail(request: Request, user_id: int):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - user_id identifies the user to inspect.
      postconditions:
        - Returns usage and content-free activity for the requested user.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Admins need operational visibility into tokens/activity without message-content access.
      WHEN TO USE it:
        - Use it from admin user detail panels.
      WHEN NOT TO USE it:
        - Do not use it to expose private messages.
      WHAT CAN GO WRONG:
        - No admin session exists or migrations are missing.
      WHAT COMES NEXT:
        - Add account edit controls and richer graphs later.

    TESTS:
      - compile smoke; route integration tests can be added after migration is in the test DB.

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as admin/dev and retry.
          common_causes:
            - missing session
          recovery_steps:
            - Sign in again.
          retry_safe: true

    CODE:
    """
    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        usage_summary = read_dcx_user_usage_summary(user_id=user_id)
        activity_events = read_dcx_user_activity_events(user_id=user_id)
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_USER_DETAIL_READ_FAILED",
                    "message": "We could not load that DCX user detail just now.",
                    "suggested_action": "Retry after backend/database health is restored.",
                },
            },
        )

    return {
        "ok": True,
        "data": {
            "user_id": user_id,
            "usage": usage_summary,
            "activity": activity_events,
        },
        "context": {
            "surface": "admin",
            "view": "user_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
