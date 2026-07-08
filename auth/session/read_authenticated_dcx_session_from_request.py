"""
CONTEXT:
This file reads the authenticated DCX browser session from one incoming HTTP request.
It exists so app and admin routes can resolve the same session cookie into one durable user
identity context instead of depending on temporary debug query parameters.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2
from fastapi import Request

from auth.session.hash_dcx_auth_session_token import hash_dcx_auth_session_token
from auth.session.read_dcx_auth_session_cookie_settings import (
    read_dcx_auth_session_cookie_settings,
)
from auth.authorization.read_dcx_user_role_may_access_admin import (
    read_dcx_user_role_may_access_admin,
)
from storage.db_config import DB_CONFIG


def read_authenticated_dcx_session_from_request(
    request: Request,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - request is one incoming HTTP request from the DCX API boundary.
        - The configured database is reachable when a session cookie is present.
      postconditions:
        - Returns one authenticated session payload when the cookie maps to an active unexpired session.
        - Touches the session/user last-seen timestamp at most every few minutes.
        - Returns null when no valid session is present.
      side_effects:
        - may update stephen_dcx_user_auth_sessions.last_seen_at_ts_ms
        - may update stephen_dcx_users.last_seen_at_ts_ms
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - App and admin routes need one shared way to resolve the current browser session.
      WHEN TO USE it:
        - Use it at authenticated route boundaries.
      WHEN NOT TO USE it:
        - Do not use it for password hashes or public build tokens.
      WHAT CAN GO WRONG:
        - Missing cookie means no authenticated session.
        - Stale or revoked session rows should be ignored.
        - Database reads can fail.
      WHAT COMES NEXT:
        - Authorization helpers can project this payload into user-only or admin-only route guards.

    TESTS:
      - returns_none_when_cookie_missing
      - returns_session_payload_when_active_cookie_matches_database_row

    ERRORS:
      - API_DCX_AUTH_SESSION_READ_FAILED:
          suggested_action: Confirm backend/database health and retry once the session store is available.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true

    CODE:
    """
    cookie_settings = read_dcx_auth_session_cookie_settings()
    raw_session_token = request.cookies.get(cookie_settings["cookie_name"])
    if raw_session_token in {None, ""}:
        return None

    now_ts_ms = int(time.time() * 1000)
    session_token_hash = hash_dcx_auth_session_token(raw_session_token)
    connect = connect_to_database or psycopg2.connect

    touch_interval_ms = 5 * 60 * 1000
    effective_last_seen_at_ts_ms = None

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        s.id,
                        s.user_id,
                        s.issued_at_ts_ms,
                        s.expires_at_ts_ms,
                        s.last_seen_at_ts_ms,
                        u.user_uuid,
                        primary_email_contact_method.normalized_value,
                        u.user_role,
                        u.account_status,
                        tz.id,
                        tz.iana_name,
                        tz.display_label
                    FROM stephen_dcx_user_auth_sessions s
                    INNER JOIN stephen_dcx_users u
                      ON u.id = s.user_id
                    LEFT JOIN stephen_dcx_timezones tz
                      ON tz.id = u.preferred_timezone_id
                     AND tz.is_active = TRUE
                    LEFT JOIN LATERAL (
                        SELECT normalized_value
                        FROM stephen_dcx_users_contact_methods
                        WHERE user_id = u.id
                          AND contact_type = %s
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) primary_email_contact_method
                      ON TRUE
                    WHERE s.session_token_hash = %s
                      AND s.session_status = %s
                      AND s.revoked_at_ts_ms IS NULL
                      AND s.expires_at_ts_ms > %s
                    LIMIT 1
                    """,
                    (
                        "email",
                        session_token_hash,
                        "active",
                        now_ts_ms,
                    ),
                )
                session_row = cursor.fetchone()
                if session_row is not None:
                    effective_last_seen_at_ts_ms = session_row[4]
                    if (
                        effective_last_seen_at_ts_ms is None
                        or effective_last_seen_at_ts_ms < now_ts_ms - touch_interval_ms
                    ):
                        cursor.execute(
                            """
                            UPDATE stephen_dcx_user_auth_sessions
                            SET last_seen_at_ts_ms = %s
                            WHERE id = %s
                            """,
                            (now_ts_ms, session_row[0]),
                        )
                        cursor.execute(
                            """
                            UPDATE stephen_dcx_users
                            SET last_seen_at_ts_ms = %s
                            WHERE id = %s
                            """,
                            (now_ts_ms, session_row[1]),
                        )
                        effective_last_seen_at_ts_ms = now_ts_ms
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_AUTH_SESSION_READ_FAILED") from exc

    if session_row is None:
        return None

    user_role = session_row[7]

    return {
        "session_id": session_row[0],
        "user_id": session_row[1],
        "issued_at_ts_ms": session_row[2],
        "expires_at_ts_ms": session_row[3],
        "last_seen_at_ts_ms": effective_last_seen_at_ts_ms,
        "user_uuid": str(session_row[5]),
        "primary_email": session_row[6],
        "user_role": user_role,
        "account_status": session_row[8],
        "preferred_timezone": (
            {
                "id": session_row[9],
                "iana_name": session_row[10],
                "display_label": session_row[11],
            }
            if session_row[9] is not None
            else None
        ),
        "may_access_app": True,
        "may_access_admin": read_dcx_user_role_may_access_admin(user_role),
    }
