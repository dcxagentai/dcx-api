"""
CONTEXT:
This file owns the first admin-facing users list HTTP boundary.
It exists so `admin.dcxagent.ai/users` can render a real user-management list before
the durable auth, role, and permission system is wired in.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from admin.users.read_dcx_admin_user_list import read_dcx_admin_user_list_capability
from routes.admin.dcx_api_routes_admin_support import (
    read_permitted_local_debug_admin_user_id_or_error_response,
)

dcx_api_routes_admin_users_list_router = APIRouter(prefix="/admin", tags=["admin"])


@dcx_api_routes_admin_users_list_router.get("/users/list", response_model=None)
def get_dcx_admin_users_list(
    admin_user_id: int | None = Query(default=None, ge=1),
):
    """
    CONTRACT:
      preconditions:
        - Real admin auth is not wired yet, so local development may temporarily supply one
          `admin_user_id` query parameter for screen testing.
      postconditions:
        - Returns a canonical success wrapper containing the current DCX user list.
        - Returns a canonical error wrapper when no temporary local admin identity is supplied yet.
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
        - No temporary local admin identity is present yet.
        - Database reads can fail.
      WHAT COMES NEXT:
        - Replace the temporary local `admin_user_id` path with real admin session/role checks
          while keeping the frontend contract stable.

    TESTS:
      - test_admin_users_list_route_returns_users_payload_for_local_debug_admin_user_id
      - test_admin_users_list_route_returns_auth_required_without_debug_identity
      - test_admin_users_list_route_rejects_debug_identity_outside_local_runtime

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Use `?admin_user_id=` locally until admin auth is connected.
          common_causes:
            - no authenticated admin session yet
          recovery_steps:
            - Add `?admin_user_id=<existing_user_id>` during local development.
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
    _, error_response = read_permitted_local_debug_admin_user_id_or_error_response(admin_user_id)
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
            "identity_resolution_mode": "temporary_admin_user_id_query_parameter",
        },
    }
