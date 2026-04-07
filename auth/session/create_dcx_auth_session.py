"""
CONTEXT:
This file creates one durable DCX authenticated session row and returns the raw token.
It exists so the first email/password login flow can issue one opaque browser session shared by
the app and admin subdomains.
"""

from __future__ import annotations

import secrets
import time
from typing import Any, Callable

import psycopg2

from auth.session.hash_dcx_auth_session_token import hash_dcx_auth_session_token
from auth.session.read_dcx_auth_session_cookie_settings import (
    read_dcx_auth_session_cookie_settings,
)
from storage.db_config import DB_CONFIG


def create_dcx_auth_session(
    authenticated_user_id: int,
    created_from_ip: str | None,
    created_from_user_agent: str | None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one existing DCX user.
        - The configured database is reachable.
      postconditions:
        - Inserts one active auth session row for the user.
        - Returns the raw session token plus its expiry metadata for the caller to place in a cookie.
      side_effects:
        - writes one row into stephen_dcx_user_auth_sessions
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: session rows are append-only per login event, so no explicit lock is required

    NARRATIVE:
      WHY this exists:
        - Browser login needs one durable session model that can later be revoked on logout or password reset.
      WHEN TO USE it:
        - Use it after validating an email/password login.
      WHEN NOT TO USE it:
        - Do not use it to authenticate a request by itself.
      WHAT CAN GO WRONG:
        - Database writes can fail.
      WHAT COMES NEXT:
        - The route can set the returned raw token into the shared app/admin cookie.

    TESTS:
      - creates_session_row_and_returns_raw_token_metadata

    ERRORS:
      - API_DCX_AUTH_SESSION_CREATE_FAILED:
          suggested_action: Confirm database health and retry the login once the backend is stable.
          common_causes:
            - database unavailable
            - insert failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: false

    CODE:
    """
    connect = connect_to_database or psycopg2.connect
    cookie_settings = read_dcx_auth_session_cookie_settings()
    now_ts_ms = int(time.time() * 1000)
    expires_at_ts_ms = now_ts_ms + (cookie_settings["max_age_seconds"] * 1000)
    raw_session_token = secrets.token_urlsafe(48)
    session_token_hash = hash_dcx_auth_session_token(raw_session_token)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_user_auth_sessions (
                        user_id,
                        session_token_hash,
                        session_status,
                        issued_at_ts_ms,
                        expires_at_ts_ms,
                        last_seen_at_ts_ms,
                        created_from_ip,
                        created_from_user_agent
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        authenticated_user_id,
                        session_token_hash,
                        "active",
                        now_ts_ms,
                        expires_at_ts_ms,
                        now_ts_ms,
                        created_from_ip,
                        created_from_user_agent,
                    ),
                )
                session_row = cursor.fetchone()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_AUTH_SESSION_CREATE_FAILED") from exc

    return {
        "session_id": session_row[0],
        "raw_session_token": raw_session_token,
        "session_token_hash": session_token_hash,
        "issued_at_ts_ms": now_ts_ms,
        "expires_at_ts_ms": expires_at_ts_ms,
    }
