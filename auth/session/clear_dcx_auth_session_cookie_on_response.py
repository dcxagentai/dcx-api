"""
CONTEXT:
This file clears the DCX authenticated session cookie from one HTTP response.
It exists so logout and future session-revocation flows can remove the browser cookie using the
same shared cookie contract as login.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse

from auth.session.read_dcx_auth_session_cookie_settings import (
    read_dcx_auth_session_cookie_settings,
)


def clear_dcx_auth_session_cookie_on_response(response: JSONResponse) -> None:
    """
    CONTRACT:
      preconditions:
        - response is the outgoing HTTP response that should clear the auth cookie.
      postconditions:
        - Deletes the configured DCX auth cookie from the response.
      side_effects:
        - mutates one HTTP response object by adding one cookie-deletion header
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: none needed because only one response object is mutated

    NARRATIVE:
      WHY this exists:
        - Logout should reliably remove the browser-visible session handle.
      WHEN TO USE it:
        - Use it when logging out or invalidating the current browser session.
      WHEN NOT TO USE it:
        - Do not use it to issue a new session cookie.
      WHAT CAN GO WRONG:
        - Cookie settings can mismatch the original cookie and leave a stale browser cookie behind.
      WHAT COMES NEXT:
        - Login continues to use the paired set-cookie helper.

    TESTS:
      - covered_indirectly_by_auth_logout_route_tests

    ERRORS: []

    CODE:
    """
    cookie_settings = read_dcx_auth_session_cookie_settings()
    response.delete_cookie(
        key=cookie_settings["cookie_name"],
        domain=cookie_settings["cookie_domain"],
        path=cookie_settings["cookie_path"],
        secure=cookie_settings["cookie_secure"],
        httponly=cookie_settings["cookie_http_only"],
        samesite=cookie_settings["cookie_same_site"],
    )
