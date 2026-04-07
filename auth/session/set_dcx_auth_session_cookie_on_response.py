"""
CONTEXT:
This file sets the authenticated DCX session cookie on one HTTP response.
It exists so the login boundary can issue the shared app/admin browser session without duplicating
cookie settings inline in route files.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse

from auth.session.read_dcx_auth_session_cookie_settings import (
    read_dcx_auth_session_cookie_settings,
)


def set_dcx_auth_session_cookie_on_response(
    response: JSONResponse,
    raw_session_token: str,
) -> None:
    """
    CONTRACT:
      preconditions:
        - response is the outgoing HTTP response that should carry the auth cookie.
        - raw_session_token is the new opaque session token issued by the backend.
      postconditions:
        - Sets the configured DCX auth cookie on the response.
      side_effects:
        - mutates one HTTP response object by adding one Set-Cookie header
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: none needed because only one response object is mutated

    NARRATIVE:
      WHY this exists:
        - Login should issue one cookie contract consistently across subdomains.
      WHEN TO USE it:
        - Use it after a successful email/password login.
      WHEN NOT TO USE it:
        - Do not use it to clear a cookie.
      WHAT CAN GO WRONG:
        - Cookie settings can be misconfigured for the current hostname.
      WHAT COMES NEXT:
        - Logout can use the paired clear-cookie helper.

    TESTS:
      - covered_indirectly_by_auth_login_route_tests

    ERRORS: []

    CODE:
    """
    cookie_settings = read_dcx_auth_session_cookie_settings()
    response.set_cookie(
        key=cookie_settings["cookie_name"],
        value=raw_session_token,
        max_age=cookie_settings["max_age_seconds"],
        httponly=cookie_settings["cookie_http_only"],
        secure=cookie_settings["cookie_secure"],
        samesite=cookie_settings["cookie_same_site"],
        domain=cookie_settings["cookie_domain"],
        path=cookie_settings["cookie_path"],
    )
