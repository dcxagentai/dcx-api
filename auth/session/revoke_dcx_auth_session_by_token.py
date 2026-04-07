"""
CONTEXT:
This file revokes one DCX authenticated session identified by its raw browser token.
It exists so logout can invalidate the current session server-side before clearing the browser cookie.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2

from auth.session.hash_dcx_auth_session_token import hash_dcx_auth_session_token
from storage.db_config import DB_CONFIG


def revoke_dcx_auth_session_by_token(
    raw_session_token: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - raw_session_token is the opaque browser session token.
        - The configured database is reachable.
      postconditions:
        - Marks the matching active session revoked when it exists.
        - Returns one payload describing whether a session row was changed.
      side_effects:
        - may update one stephen_dcx_user_auth_sessions row
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: raw_session_token
      locks: []
      contention_strategy: single-row update by unique token hash keeps repeated revocations safe

    NARRATIVE:
      WHY this exists:
        - Logout should invalidate the current session server-side, not just clear the browser cookie.
      WHEN TO USE it:
        - Use it from logout or future forced-session-revocation flows.
      WHEN NOT TO USE it:
        - Do not use it for bulk password-reset session revocation.
      WHAT CAN GO WRONG:
        - Missing session rows should be treated as already logged out.
        - Database writes can fail.
      WHAT COMES NEXT:
        - Password reset can later revoke all sessions for the user.

    TESTS:
      - revokes_active_session_when_token_matches_row

    ERRORS:
      - API_DCX_AUTH_SESSION_REVOKE_FAILED:
          suggested_action: Confirm backend/database health and retry the logout after the session store is available.
          common_causes:
            - database unavailable
            - update failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true

    CODE:
    """
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = int(time.time() * 1000)
    session_token_hash = hash_dcx_auth_session_token(raw_session_token)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE stephen_dcx_user_auth_sessions
                    SET
                        session_status = %s,
                        revoked_at_ts_ms = %s
                    WHERE session_token_hash = %s
                      AND session_status = %s
                      AND revoked_at_ts_ms IS NULL
                    RETURNING id
                    """,
                    (
                        "revoked",
                        now_ts_ms,
                        session_token_hash,
                        "active",
                    ),
                )
                updated_row = cursor.fetchone()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_AUTH_SESSION_REVOKE_FAILED") from exc

    return {
        "session_revoked": updated_row is not None,
    }
