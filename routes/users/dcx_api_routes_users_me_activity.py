"""
CONTEXT:
This file owns the DCX app-facing `/users/me/activity` HTTP boundary.
It exists so users can inspect a content-free timeline of their own account activity.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from activity.read_dcx_user_activity_events import read_dcx_user_activity_events

dcx_api_routes_users_me_activity_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_activity_router.get("/me/activity", response_model=None)
def get_authenticated_dcx_user_activity(request: Request):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session cookie is present.
      postconditions:
        - Returns recent content-free activity events for the current user.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Users should see what happened on their account without admins seeing private content.
      WHEN TO USE it:
        - Use it from the app Activity screen.
      WHEN NOT TO USE it:
        - Do not use it for message-content inspection.
      WHAT CAN GO WRONG:
        - No session is present or activity tables have not been migrated.
      WHAT COMES NEXT:
        - Add pagination and richer event labels.

    TESTS:
      - compile smoke; route integration tests can be added after the migration is in the test DB.

    ERRORS:
      - API_DCX_USER_ACTIVITY_READ_FAILED:
          suggested_action: Apply migrations and retry after backend/database health is restored.
          common_causes:
            - missing activity table
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

    try:
        activity_events = read_dcx_user_activity_events(user_id=authenticated_user_id)
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_USER_ACTIVITY_READ_FAILED",
                    "message": "We could not load DCX activity just now.",
                    "suggested_action": "Retry after backend/database health is restored.",
                },
            },
        )

    return {
        "ok": True,
        "data": activity_events,
        "context": {
            "surface": "app",
            "view": "activity",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
