"""
CONTEXT:
This file projects one authenticated DCX browser session into a narrow frontend-facing summary.
It exists so app and admin bootstraps can ask one shared `/auth/session` route whether the current
browser already has a valid session and what surfaces that session may access.
"""

from __future__ import annotations

from fastapi import Request

from auth.session.read_authenticated_dcx_session_from_request import (
    read_authenticated_dcx_session_from_request,
)


def read_authenticated_dcx_session_summary(request: Request) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - request is the current HTTP request.
      postconditions:
        - Returns one narrow session summary when the request carries a valid authenticated session.
        - Returns null when the request is not authenticated.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Frontend shells need a compact session summary rather than the full session row.
      WHEN TO USE it:
        - Use it from the `/auth/session` route.
      WHEN NOT TO USE it:
        - Do not use it for route authorization decisions that need richer error handling.
      WHAT CAN GO WRONG:
        - No valid session cookie may be present.
      WHAT COMES NEXT:
        - App/admin bootstraps can redirect unauthenticated users to login.

    TESTS:
      - covered_indirectly_by_auth_session_route_tests

    ERRORS:
      - API_DCX_AUTH_SESSION_READ_FAILED:
          suggested_action: Retry after the backend is healthy.
          common_causes:
            - database unavailable
          recovery_steps:
            - Verify backend/database health.
            - Retry.
          retry_safe: true

    CODE:
    """
    authenticated_session = read_authenticated_dcx_session_from_request(request)
    if authenticated_session is None:
        return None

    return {
        "user_id": authenticated_session["user_id"],
        "user_uuid": authenticated_session["user_uuid"],
        "primary_email": authenticated_session["primary_email"],
        "user_role": authenticated_session["user_role"],
        "account_status": authenticated_session["account_status"],
        "allowed_surfaces": {
            "app": authenticated_session["may_access_app"],
            "admin": authenticated_session["may_access_admin"],
        },
        "session": {
            "session_id": authenticated_session["session_id"],
            "issued_at_ts_ms": authenticated_session["issued_at_ts_ms"],
            "expires_at_ts_ms": authenticated_session["expires_at_ts_ms"],
            "last_seen_at_ts_ms": authenticated_session["last_seen_at_ts_ms"],
        },
    }
