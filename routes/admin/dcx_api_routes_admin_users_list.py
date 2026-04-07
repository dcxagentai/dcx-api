"""
CONTEXT:
This file owns the first admin-facing users list HTTP boundary.
It exists so `admin.dcxagent.ai/users` can render a real user-management list before
the internal workspace grows beyond its first MVP tools.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)
from admin.users.read_dcx_admin_user_list import read_dcx_admin_user_list_capability

dcx_api_routes_admin_users_list_router = APIRouter(prefix="/admin", tags=["admin"])


@dcx_api_routes_admin_users_list_router.get("/users/list", response_model=None)
def get_dcx_admin_users_list(
    request: Request,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
      postconditions:
        - Returns a canonical success wrapper containing the current DCX user list.
        - Returns a canonical error wrapper when no authenticated admin/dev session is available.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first admin surface should be a real read-only list of users rather than a fake shell.
      WHEN TO USE it:
        - Use it from the initial admin users screen only.
      WHEN NOT TO USE it:
        - Do not treat this as the final admin authorization design.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - Database reads can fail.
      WHAT COMES NEXT:
        - Keep this route stable while more authenticated admin surfaces are added.

    TESTS:
      - test_admin_users_list_route_returns_users_payload_for_authenticated_admin_session
      - test_admin_users_list_route_returns_auth_required_without_authenticated_session

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as an admin/dev user, then retry.
          common_causes:
            - no authenticated admin/dev session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the admin login screen.
          retry_safe: true
      - API_DCX_ADMIN_USERS_LIST_READ_FAILED:
          suggested_action: Retry after backend/database health is restored.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify backend/database health.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        user_list = read_dcx_admin_user_list_capability()
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_USERS_LIST_READ_FAILED",
                    "message": "We could not load the DCX admin users list just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": user_list,
        "context": {
            "surface": "admin",
            "view": "users_list",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
