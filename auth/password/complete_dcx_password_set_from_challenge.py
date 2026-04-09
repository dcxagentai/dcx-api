"""
CONTEXT:
This file completes one DCX password setup or reset from a one-time challenge token.
It exists so signup-completion and forgotten-password flows can converge on one secure password
write path that validates the token, hashes the password, and consumes the challenge row.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from auth.password.create_dcx_password_hash import create_dcx_password_hash
from auth.password.dcx_password_link_challenge_support import (
    DCX_PASSWORD_LINK_CHALLENGE_TYPE,
    hash_dcx_password_link_challenge_token,
    normalize_dcx_password_link_challenge_token,
)
from auth.password.validate_dcx_candidate_password import validate_dcx_candidate_password
from storage.db_config import DB_CONFIG


def complete_dcx_password_set_from_challenge(
    raw_password_link_token: str,
    candidate_password: str,
    confirmed_password: str,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - raw_password_link_token came from one app password-set page hash fragment.
        - candidate_password and confirmed_password are the submitted plaintext values.
        - The configured database is reachable.
      postconditions:
        - Validates the token and password policy.
        - Creates or updates the durable password credential row for the user.
        - Consumes the active password-link challenge row.
        - Revokes all previously active sessions for the user inside the same committed write path.
      side_effects:
        - writes to stephen_dcx_user_password_credentials
        - writes to stephen_dcx_user_auth_challenges
        - writes to stephen_dcx_user_auth_sessions
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: complete_password_set:{password_link_token_hash}
      locks:
        - row lock on the active password-link challenge row
        - row lock on the target password credential row when it exists
      contention_strategy: serialize on the active challenge row, then upsert the single password-credential row for the user and revoke active sessions in the same transaction

    NARRATIVE:
      WHY this exists:
        - The password-set page should have one canonical backend completion path regardless of whether the token came from signup or reset.
      WHEN TO USE it:
        - Use it from the app-side password-set form submission.
      WHEN NOT TO USE it:
        - Do not use it for ordinary login or authenticated account edits.
      WHAT CAN GO WRONG:
        - The token can be missing, stale, or already consumed.
        - The password can fail validation.
        - The database can fail while writing the new credential.
      WHAT COMES NEXT:
        - The browser can redirect the user to the shared `/login` page and ask them to sign in with the new password.

    TESTS:
      - complete_password_set_creates_password_credential_and_consumes_challenge
      - complete_password_set_rejects_expired_challenge

    ERRORS:
      - API_DCX_PASSWORD_LINK_TOKEN_INVALID:
          suggested_action: Use the newest password link or request another one.
          common_causes:
            - missing token
            - malformed token
          recovery_steps:
            - Reopen the newest password link.
            - Or request another reset email.
          retry_safe: true
      - API_DCX_PASSWORD_CHALLENGE_NOT_FOUND:
          suggested_action: Request a fresh password link and retry.
          common_causes:
            - token already consumed
            - token already invalidated
            - token never existed
          recovery_steps:
            - Start the password flow again.
            - Use the newest link only once.
          retry_safe: true
      - API_DCX_PASSWORD_CHALLENGE_EXPIRED:
          suggested_action: Request a fresh password link and retry.
          common_causes:
            - link older than the password challenge lifetime
          recovery_steps:
            - Request another link.
            - Retry with the new email.
          retry_safe: true
      - API_DCX_PASSWORD_SET_PERSISTENCE_FAILED:
          suggested_action: Confirm database health and retry once the backend is stable.
          common_causes:
            - database unavailable
            - transaction failure
          recovery_steps:
            - Verify database connectivity.
            - Retry the submission.
          retry_safe: true

    CODE:
    """
    normalized_password_link_token = normalize_dcx_password_link_challenge_token(
        raw_password_link_token
    )
    normalized_candidate_password = validate_dcx_candidate_password(
        candidate_password=candidate_password,
        confirmed_password=confirmed_password,
    )["normalized_candidate_password"]
    password_link_token_hash = hash_dcx_password_link_challenge_token(
        normalized_password_link_token
    )
    next_password_hash = create_dcx_password_hash(normalized_candidate_password)
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        challenge_purpose,
                        expires_at_ts_ms
                    FROM stephen_dcx_user_auth_challenges
                    WHERE challenge_type = %s
                      AND otp_hash = %s
                      AND challenge_status = %s
                      AND consumed_at_ts_ms IS NULL
                      AND invalidated_at_ts_ms IS NULL
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        DCX_PASSWORD_LINK_CHALLENGE_TYPE,
                        password_link_token_hash,
                        "pending",
                    ),
                )
                challenge_row = cursor.fetchone()

                if challenge_row is None:
                    raise RuntimeError("API_DCX_PASSWORD_CHALLENGE_NOT_FOUND")

                challenge_id = challenge_row[0]
                authenticated_user_id = challenge_row[1]
                challenge_purpose = challenge_row[2]
                expires_at_ts_ms = challenge_row[3]

                if expires_at_ts_ms < now_ts_ms:
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_user_auth_challenges
                        SET
                            challenge_status = %s,
                            invalidated_at_ts_ms = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            "expired",
                            now_ts_ms,
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
                    raise RuntimeError("API_DCX_PASSWORD_CHALLENGE_EXPIRED")

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_user_password_credentials (
                        user_id,
                        password_hash,
                        password_algorithm,
                        password_set_at_ts_ms,
                        password_reset_required,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET
                        password_hash = EXCLUDED.password_hash,
                        password_algorithm = EXCLUDED.password_algorithm,
                        password_set_at_ts_ms = EXCLUDED.password_set_at_ts_ms,
                        password_reset_required = FALSE,
                        updated_at_ts_ms = EXCLUDED.updated_at_ts_ms
                    """,
                    (
                        authenticated_user_id,
                        next_password_hash,
                        "argon2id",
                        now_ts_ms,
                        False,
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_user_auth_challenges
                    SET
                        consumed_at_ts_ms = %s,
                        challenge_status = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (
                        now_ts_ms,
                        "consumed",
                        now_ts_ms,
                        challenge_id,
                    ),
                )
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
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_PASSWORD_SET_PERSISTENCE_FAILED") from exc

    return {
        "user_id": authenticated_user_id,
        "challenge_purpose": challenge_purpose,
        "password_set_at_ts_ms": now_ts_ms,
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
