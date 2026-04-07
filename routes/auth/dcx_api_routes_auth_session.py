"""
CONTEXT:
This file owns the shared DCX authenticated-session summary HTTP boundary.
It exists so app and admin frontends can bootstrap themselves from one canonical session-check
route before rendering protected surfaces.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.session.read_authenticated_dcx_session_summary import (
    read_authenticated_dcx_session_summary,
)

dcx_api_routes_auth_session_router = APIRouter(prefix="/auth", tags=["auth"])


@dcx_api_routes_auth_session_router.get("/session", response_model=None)
def get_dcx_authenticated_session_summary(request: Request):
    """
    CONTRACT:
      preconditions:
        - The request may or may not carry the shared DCX session cookie.
      postconditions:
        - Returns a canonical success wrapper when the current browser session is authenticated.
        - Returns a canonical auth-required wrapper when no valid session exists.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - App and admin both need one stable “who am I?” route.
      WHEN TO USE it:
        - Use it during frontend bootstrap and route guarding.
      WHEN NOT TO USE it:
        - Do not use it as a substitute for route-level authorization.
      WHAT CAN GO WRONG:
        - No valid session cookie may be present.
      WHAT COMES NEXT:
        - Logout and protected routes can build on the same cookie/session contract.

    TESTS:
      - covered_indirectly_by_auth_session_route_tests

    ERRORS:
      - API_DCX_AUTH_SESSION_REQUIRED:
          suggested_action: Sign in to create a DCX session first.
          common_causes:
            - no session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again.
          retry_safe: true

    CODE:
    """
    authenticated_session_summary = read_authenticated_dcx_session_summary(request)
    if authenticated_session_summary is None:
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_AUTH_SESSION_REQUIRED",
                    "message": "No authenticated DCX session is active.",
                    "suggested_action": "Sign in to create a DCX session first.",
                },
            },
        )

    return {
        "ok": True,
        "data": authenticated_session_summary,
        "context": {
            "surface": "shared_auth",
            "view": "session_summary",
            "auth_mode": "session_cookie",
        },
    }
