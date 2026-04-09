"""
CONTEXT:
This file owns the shared DCX logout HTTP boundary.
It exists so app and admin can both invalidate the current browser session using one calm
idempotent backend contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.logout.logout_authenticated_dcx_user import logout_authenticated_dcx_user
from auth.session.clear_dcx_auth_session_cookie_on_response import (
    clear_dcx_auth_session_cookie_on_response,
)
from auth.session.read_dcx_auth_session_cookie_settings import (
    read_dcx_auth_session_cookie_settings,
)

dcx_api_routes_auth_logout_router = APIRouter(prefix="/auth", tags=["auth"])


@dcx_api_routes_auth_logout_router.post("/logout", response_model=None)
def post_dcx_auth_logout(request: Request):
    """
    CONTRACT:
      preconditions:
        - The request may or may not carry the shared DCX session cookie.
      postconditions:
        - Returns a canonical success wrapper describing the logout result.
        - Clears the shared auth cookie from the response.
      side_effects:
        - may revoke one auth session row
        - mutates the outgoing response with one cookie-deletion header
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Logout should be one shared stable operation across app and admin.
      WHEN TO USE it:
        - Use it from the app/admin logout actions.
      WHEN NOT TO USE it:
        - Do not use it for global session revocation after password reset.
      WHAT CAN GO WRONG:
        - Session revoke can fail if the backend is unhealthy.
      WHAT COMES NEXT:
        - Password reset can later revoke all sessions in one separate capability.

    TESTS:
      - covered_indirectly_by_auth_logout_route_tests

    ERRORS: []

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    cookie_settings = read_dcx_auth_session_cookie_settings()
    raw_session_token = request.cookies.get(cookie_settings["cookie_name"])
    logout_result = logout_authenticated_dcx_user(raw_session_token)

    response = JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "data": logout_result,
            "context": {
                "surface": "shared_auth",
                "view": "logout",
                "auth_mode": "session_cookie",
            },
        },
    )
    clear_dcx_auth_session_cookie_on_response(response)
    return response
