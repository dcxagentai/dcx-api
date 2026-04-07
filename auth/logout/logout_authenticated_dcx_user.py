"""
CONTEXT:
This file logs out the currently authenticated DCX browser session.
It exists so app and admin can both revoke the current server-side session with one shared
capability before clearing the browser cookie.
"""

from __future__ import annotations

from auth.session.revoke_dcx_auth_session_by_token import revoke_dcx_auth_session_by_token


def logout_authenticated_dcx_user(raw_session_token: str | None) -> dict:
    """
    CONTRACT:
      preconditions:
        - raw_session_token is the current browser session token or null.
      postconditions:
        - Returns one stable logout payload.
        - Revokes the server-side session when a token is present.
      side_effects:
        - may update one auth session row
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: raw_session_token or 'no_session'
      locks: []
      contention_strategy: single-row session revocation is already idempotent

    NARRATIVE:
      WHY this exists:
        - Logout should be a calm idempotent operation whether or not a session is still active.
      WHEN TO USE it:
        - Use it from the auth logout route.
      WHEN NOT TO USE it:
        - Do not use it for global revoke-all-sessions flows.
      WHAT CAN GO WRONG:
        - Database revoke can fail.
      WHAT COMES NEXT:
        - The route can clear the browser cookie regardless of whether a row changed.

    TESTS:
      - logout_returns_logged_out_true_even_without_session_token
      - logout_revokes_current_session_when_token_present

    ERRORS:
      - API_DCX_AUTH_SESSION_REVOKE_FAILED:
          suggested_action: Retry the logout after the backend is healthy.
          common_causes:
            - database unavailable
          recovery_steps:
            - Verify backend/database health.
            - Retry.
          retry_safe: true

    CODE:
    """
    if raw_session_token in {None, ""}:
        return {
            "logged_out": True,
            "session_revoked": False,
        }

    revoke_result = revoke_dcx_auth_session_by_token(raw_session_token)
    return {
        "logged_out": True,
        "session_revoked": revoke_result["session_revoked"],
    }
