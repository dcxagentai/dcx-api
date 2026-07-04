"""
CONTEXT:
This file resolves one authenticated DCX admin-capable user id or returns one canonical HTTP error
response. It exists so admin-facing routes can enforce one shared session-cookie plus role gate as
the stable internal authorization boundary.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from auth.session.read_authenticated_dcx_session_from_request import (
    read_authenticated_dcx_session_from_request,
)


def read_authenticated_dcx_admin_user_id_or_error_response(
    request: Request,
) -> tuple[int | None, str | None, JSONResponse | None]:
    """
    CONTRACT:
      preconditions:
        - request is the current admin-facing HTTP request.
      postconditions:
        - Returns the authenticated admin-capable user id plus one identity-resolution label when a valid internal session exists.
        - Returns one canonical error response when no valid admin/dev session exists.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Admin routes now need both authentication and role enforcement, not just a raw user id.
      WHEN TO USE it:
        - Use it from authenticated admin route boundaries.
      WHEN NOT TO USE it:
        - Do not use it for normal app-only routes.
      WHAT CAN GO WRONG:
        - The session can belong to a normal user role.
        - No session cookie may be present.
      WHAT COMES NEXT:
        - Keep this helper as the stable admin-facing auth boundary while more internal tools are added.

    TESTS:
      - covered_indirectly_by_auth_and_admin_route_tests

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as an admin-capable user, then retry.
          common_causes:
            - no session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in through the real auth flow.
          retry_safe: true
      - API_DCX_ADMIN_FORBIDDEN:
          suggested_action: Sign in with an admin, dev, shareholder, or investor account to access the admin workspace.
          common_causes:
            - normal user session tried to access admin
          recovery_steps:
            - Switch to an admin-capable account.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    authenticated_session = read_authenticated_dcx_session_from_request(request)
    if authenticated_session is not None:
        if authenticated_session["may_access_admin"] is not True:
            return None, None, JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_DCX_ADMIN_FORBIDDEN",
                    "message": "This authenticated DCX user does not have admin access.",
                    "suggested_action": "Sign in with an admin, dev, shareholder, or investor account to access the admin workspace.",
                    },
                },
            )

        return authenticated_session["user_id"], "session_cookie", None

    return None, None, JSONResponse(
        status_code=401,
        content={
            "ok": False,
            "error": {
                "code": "API_DCX_ADMIN_AUTH_REQUIRED",
                "message": "No authenticated DCX admin session is active.",
                "suggested_action": "Sign in as an admin-capable user, then retry.",
            },
        },
    )
