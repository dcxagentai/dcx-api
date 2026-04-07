"""
CONTEXT:
This file resolves one authenticated DCX app user id or returns one canonical HTTP error response.
It exists so app-facing routes can trust one shared session-cookie identity gate without changing
their stable route contracts as more protected app surfaces are added.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from auth.session.read_authenticated_dcx_session_from_request import (
    read_authenticated_dcx_session_from_request,
)


def read_authenticated_dcx_user_id_or_error_response(
    request: Request,
) -> tuple[int | None, str | None, JSONResponse | None]:
    """
    CONTRACT:
      preconditions:
        - request is the current app-facing HTTP request.
      postconditions:
        - Returns the authenticated user id plus one identity-resolution label when a valid session exists.
        - Returns one canonical error response when no valid authenticated session exists.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - App routes need one shared session-backed identity gate.
      WHEN TO USE it:
        - Use it from authenticated app route boundaries.
      WHEN NOT TO USE it:
        - Do not use it for admin-only authorization.
      WHAT CAN GO WRONG:
        - No session cookie may be present.
      WHAT COMES NEXT:
        - Keep this helper as the stable app-facing auth boundary while more app routes are added.

    TESTS:
      - covered_indirectly_by_auth_and_app_route_tests

    ERRORS:
      - API_USERS_ME_AUTH_REQUIRED:
          suggested_action: Sign in through the DCX app login flow, then retry.
          common_causes:
            - no session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in through the real auth flow.
          retry_safe: true

    CODE:
    """
    authenticated_session = read_authenticated_dcx_session_from_request(request)
    if authenticated_session is not None:
        return authenticated_session["user_id"], "session_cookie", None

    return None, None, JSONResponse(
        status_code=401,
        content={
            "ok": False,
            "error": {
                "code": "API_DCX_AUTH_SESSION_REQUIRED",
                "message": "No authenticated DCX app session is active.",
                "suggested_action": "Sign in through the DCX app login flow, then retry.",
            },
        },
    )
