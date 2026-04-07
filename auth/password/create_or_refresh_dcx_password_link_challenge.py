"""
CONTEXT:
This file creates or refreshes one active DCX password-link challenge for a confirmed user identity.
It exists so signup password setup and forgotten-password reset can share the same durable one-time
token machinery without duplicating challenge-row state transitions.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from auth.password.dcx_password_link_challenge_support import (
    DCX_PASSWORD_LINK_CHALLENGE_TYPE,
    DCX_PASSWORD_LINK_TOKEN_LIFETIME_MS,
    build_dcx_password_link_challenge_token,
    build_dcx_password_set_page_url,
    hash_dcx_password_link_challenge_token,
)
from storage.db_config import DB_CONFIG


def create_or_refresh_dcx_password_link_challenge(
    authenticated_user_id: int,
    authenticated_user_identity_id: int,
    challenge_purpose: str,
    delivery_target_email: str,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    raw_token_provider: Callable[[], str] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one already confirmed DCX user.
        - authenticated_user_identity_id identifies that user's email auth identity.
        - challenge_purpose is one supported password-link purpose such as `password_setup` or `password_reset`.
        - delivery_target_email is the canonical email address for the user.
      postconditions:
        - Ensures one active pending password-link challenge exists for the user identity and purpose.
        - Rotates the challenge token and expiry each time this capability is called.
        - Returns one app-domain password-set URL carrying the raw one-time token.
      side_effects:
        - writes to stephen_dcx_user_auth_challenges
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: dcx_password_link_challenge:{authenticated_user_identity_id}:{challenge_purpose}
      locks:
        - postgres transaction-scoped advisory lock on user identity plus purpose
        - row lock on the existing active challenge row when it exists
      contention_strategy: serialize password-link creation for one identity/purpose pair, then update or insert the shared active row

    NARRATIVE:
      WHY this exists:
        - Password setup after signup and forgotten-password reset both need one durable one-time token that survives page reloads and email delays.
      WHEN TO USE it:
        - Use it immediately after signup OTP confirmation for setup, or inside the reset-request flow before sending the reset email.
      WHEN NOT TO USE it:
        - Do not use it for login sessions, OTP verification, or authenticated account saves.
      WHAT CAN GO WRONG:
        - The database can be unavailable.
        - Concurrent refreshes for the same identity and purpose can collide without a lock.
      WHAT COMES NEXT:
        - The caller can either redirect the browser straight to the returned URL or embed that URL into the password-reset email.

    TESTS:
      - creates_new_pending_password_link_challenge_when_none_exists
      - refreshes_existing_pending_password_link_challenge

    ERRORS:
      - API_DCX_PASSWORD_LINK_CHALLENGE_PERSISTENCE_FAILED:
          suggested_action: Confirm database health and retry once the backend is stable.
          common_causes:
            - database unavailable
            - transaction failure
          recovery_steps:
            - Verify database connectivity.
            - Retry the operation.
          retry_safe: true
          what_changed: unknown until the transaction outcome is inspected
          rollback_needed: false
          rollback_operation: rely on transaction rollback and inspect manually only if a partial committed write is suspected

    CODE:
    """
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()
    raw_password_link_token = (raw_token_provider or build_dcx_password_link_challenge_token)()
    password_link_token_hash = hash_dcx_password_link_challenge_token(raw_password_link_token)
    password_link_expires_at_ts_ms = now_ts_ms + DCX_PASSWORD_LINK_TOKEN_LIFETIME_MS

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"password-link:{authenticated_user_identity_id}:{challenge_purpose}",),
                )
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_user_auth_challenges
                    WHERE user_auth_identity_id = %s
                      AND challenge_type = %s
                      AND challenge_purpose = %s
                      AND challenge_status = %s
                      AND consumed_at_ts_ms IS NULL
                      AND invalidated_at_ts_ms IS NULL
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        authenticated_user_identity_id,
                        DCX_PASSWORD_LINK_CHALLENGE_TYPE,
                        challenge_purpose,
                        "pending",
                    ),
                )
                existing_row = cursor.fetchone()

                if existing_row is None:
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_user_auth_challenges (
                            user_id,
                            user_auth_identity_id,
                            challenge_type,
                            challenge_purpose,
                            delivery_target,
                            otp_hash,
                            expires_at_ts_ms,
                            sent_at_ts_ms,
                            last_attempted_at_ts_ms,
                            attempt_count,
                            max_attempt_count,
                            resend_count,
                            challenge_status,
                            created_at_ts_ms,
                            updated_at_ts_ms
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, 0, 5, 0, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            authenticated_user_id,
                            authenticated_user_identity_id,
                            DCX_PASSWORD_LINK_CHALLENGE_TYPE,
                            challenge_purpose,
                            delivery_target_email,
                            password_link_token_hash,
                            password_link_expires_at_ts_ms,
                            now_ts_ms,
                            "pending",
                            now_ts_ms,
                            now_ts_ms,
                        ),
                    )
                    challenge_id = cursor.fetchone()[0]
                else:
                    challenge_id = existing_row[0]
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_user_auth_challenges
                        SET
                            delivery_target = %s,
                            otp_hash = %s,
                            otp_salt = NULL,
                            expires_at_ts_ms = %s,
                            sent_at_ts_ms = %s,
                            last_attempted_at_ts_ms = NULL,
                            attempt_count = 0,
                            max_attempt_count = 5,
                            resend_count = resend_count + 1,
                            challenge_status = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            delivery_target_email,
                            password_link_token_hash,
                            password_link_expires_at_ts_ms,
                            now_ts_ms,
                            "pending",
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_PASSWORD_LINK_CHALLENGE_PERSISTENCE_FAILED") from exc

    return {
        "challenge_id": challenge_id,
        "raw_password_link_token": raw_password_link_token,
        "password_set_url": build_dcx_password_set_page_url(
            challenge_purpose=challenge_purpose,
            raw_password_link_token=raw_password_link_token,
        ),
        "challenge_purpose": challenge_purpose,
        "expires_at_ts_ms": password_link_expires_at_ts_ms,
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
