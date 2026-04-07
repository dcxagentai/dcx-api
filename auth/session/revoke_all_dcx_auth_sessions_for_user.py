"""
CONTEXT:
This file revokes all active DCX auth sessions for one user.
It exists so password resets and other high-trust security operations can invalidate previously
issued browser sessions immediately.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def revoke_all_dcx_auth_sessions_for_user(
    authenticated_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one existing DCX user.
      postconditions:
        - Marks all active sessions for that user as revoked.
      side_effects:
        - writes to stephen_dcx_user_auth_sessions
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: revoke_all_sessions:{authenticated_user_id}
      locks:
        - row locks on the target session rows touched by the update
      contention_strategy: rely on one scoped update statement across the user's active sessions

    NARRATIVE:
      WHY this exists:
        - Password reset should invalidate all previously issued sessions so older browser cookies stop working.
      WHEN TO USE it:
        - Use it after a successful password reset or other credential-rotation event.
      WHEN NOT TO USE it:
        - Do not use it for ordinary logout of a single current session.
      WHAT CAN GO WRONG:
        - Database write failures can leave old sessions active.
      WHAT COMES NEXT:
        - The user can sign in again with the new password and receive one fresh session.

    TESTS:
      - revokes_all_active_sessions_for_user

    ERRORS:
      - API_DCX_AUTH_SESSION_REVOKE_ALL_FAILED:
          suggested_action: Confirm database health and retry the password-reset flow.
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
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE stephen_dcx_user_auth_sessions
                    SET
                        session_status = %s,
                        revoked_at_ts_ms = %s,
                        updated_at_ts_ms = %s
                    WHERE user_id = %s
                      AND session_status = %s
                      AND revoked_at_ts_ms IS NULL
                    """,
                    (
                        "revoked",
                        now_ts_ms,
                        now_ts_ms,
                        authenticated_user_id,
                        "active",
                    ),
                )
                revoked_count = cursor.rowcount
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_AUTH_SESSION_REVOKE_ALL_FAILED") from exc

    return {
        "revoked_count": revoked_count,
        "revoked_at_ts_ms": now_ts_ms,
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
