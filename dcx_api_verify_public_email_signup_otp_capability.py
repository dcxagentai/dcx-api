"""
CONTEXT:
This file verifies the public DCX email-signup OTP using the opaque signup flow token.
It exists so the browser can complete the email confirmation journey without carrying the
email address through URL state or exposing internal challenge details back to the client.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from dcx_api_public_email_signup_otp_support import (
    PUBLIC_EMAIL_SIGNUP_ALLOWED_VERIFY_PATHS,
    PUBLIC_EMAIL_SIGNUP_CHALLENGE_PURPOSE,
    PUBLIC_EMAIL_SIGNUP_CHALLENGE_TYPE,
    PUBLIC_EMAIL_SIGNUP_LOCKOUT_MS,
    PUBLIC_EMAIL_SIGNUP_MAX_VERIFY_ATTEMPTS,
    hash_public_email_signup_flow_token,
    normalize_public_email_signup_flow_token,
    normalize_public_email_signup_language_code,
    normalize_public_email_signup_origin_header,
    normalize_public_email_signup_otp_code,
    normalize_public_email_signup_page_url,
    otp_code_matches_public_email_signup_hash,
)
from dcx_storage.db_config import DB_CONFIG


def verify_public_email_signup_otp_capability(
    signup_flow_token: str,
    otp_code: str,
    language_code: str,
    verification_page_url: str,
    origin_header: str | None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - signup_flow_token, otp_code, language_code, verification_page_url, and origin_header describe one public OTP verification request.
        - The configured database is reachable and the user-signup schema has been applied.
      postconditions:
        - Confirms the user primary email and the email auth identity when the OTP matches.
        - Consumes the active challenge row on success.
        - Increments attempt state and lockout state on failure.
      side_effects:
        - writes to stephen_dcx_users
        - writes to stephen_dcx_user_auth_identities
        - writes to stephen_dcx_user_auth_challenges
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: public_email_signup_otp_verify:{signup_flow_token_hash}
      locks:
        - row lock on the active challenge row found through the flow token hash
        - row locks on the owning user and identity
      contention_strategy: serialize verification on the active challenge row, then rely on attempt counters and consumed state transitions

    NARRATIVE:
      WHY this exists:
        - The email-signup journey is only complete once the browser proves possession of the latest OTP and the backend confirms the durable identity state.
      WHEN TO USE it:
        - Use it from `/users/signup-email/verify-otp`.
      WHEN NOT TO USE it:
        - Do not use it for initial signup or resend requests.
      WHAT CAN GO WRONG:
        - The flow token can be invalid or stale.
        - The challenge can be expired, locked, or already consumed.
        - The OTP can be wrong.
      WHAT COMES NEXT:
        - The route can return one generic confirmation success response and clear the browser flow token.

    TESTS:
      - correct_otp_confirms_user_identity_and_consumes_challenge
      - incorrect_otp_increments_attempt_count
      - final_incorrect_otp_sets_lockout_state
      - expired_or_invalid_flow_requires_restart

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_INVALID:
          suggested_action: Restart the signup flow from the public landing page.
          common_causes:
            - missing flow token
            - malformed token
          recovery_steps:
            - Return to the signup page.
            - Submit the email again.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_LANGUAGE_CODE_INVALID:
          suggested_action: Reload the localized public page and retry.
          common_causes:
            - malformed locale value
          recovery_steps:
            - Reopen the public page.
            - Retry the request.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_PAGE_URL_INVALID:
          suggested_action: Retry the request from the intended DCX verification page.
          common_causes:
            - wrong page path
            - origin mismatch
          recovery_steps:
            - Reopen the official verification page.
            - Retry the request.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_OTP_INVALID:
          suggested_action: Enter the six-digit code from the latest email and retry.
          common_causes:
            - malformed OTP
          recovery_steps:
            - Re-copy the newest code.
            - Retry verification.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED:
          suggested_action: Restart the signup flow from the public landing page.
          common_causes:
            - expired or missing active challenge
            - already consumed or invalidated token
          recovery_steps:
            - Return to the signup page.
            - Submit the email again.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED:
          suggested_action: Request a new code or restart the signup flow.
          common_causes:
            - wrong OTP
            - expired OTP
            - locked challenge
          recovery_steps:
            - Use resend if available.
            - Otherwise restart signup.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFY_PERSISTENCE_FAILED:
          suggested_action: Confirm database health and retry once the backend is stable.
          common_causes:
            - database unavailable
            - transaction failure
          recovery_steps:
            - Verify database health.
            - Retry the request.
          retry_safe: true
          what_changed: unknown until the transaction outcome is inspected
          rollback_needed: false
          rollback_operation: rely on the transaction rollback; inspect manually only if a partial committed write is suspected

    CODE:
    """
    normalized_origin = normalize_public_email_signup_origin_header(origin_header)
    normalized_language_code = normalize_public_email_signup_language_code(
        language_code=language_code,
        invalid_error_code="API_PUBLIC_EMAIL_SIGNUP_LANGUAGE_CODE_INVALID",
    )
    normalized_verification_page_url = normalize_public_email_signup_page_url(
        page_url=verification_page_url,
        expected_origin=normalized_origin,
        allowed_paths=PUBLIC_EMAIL_SIGNUP_ALLOWED_VERIFY_PATHS,
        invalid_error_code="API_PUBLIC_EMAIL_SIGNUP_PAGE_URL_INVALID",
    )
    normalized_flow_token = normalize_public_email_signup_flow_token(
        flow_token=signup_flow_token,
        invalid_error_code="API_PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_INVALID",
    )
    normalized_otp_code = normalize_public_email_signup_otp_code(
        otp_code=otp_code,
        invalid_error_code="API_PUBLIC_EMAIL_SIGNUP_OTP_INVALID",
    )
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()
    flow_token_hash = hash_public_email_signup_flow_token(normalized_flow_token)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        user_auth_identity_id,
                        otp_hash,
                        otp_salt,
                        expires_at_ts_ms,
                        attempt_count,
                        max_attempt_count,
                        locked_until_ts_ms,
                        public_signup_flow_token_expires_at_ts_ms,
                        challenge_status,
                        delivery_target
                    FROM stephen_dcx_user_auth_challenges
                    WHERE public_signup_flow_token_hash = %s
                      AND challenge_type = %s
                      AND challenge_purpose = %s
                      AND challenge_status = %s
                      AND consumed_at_ts_ms IS NULL
                      AND invalidated_at_ts_ms IS NULL
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        flow_token_hash,
                        PUBLIC_EMAIL_SIGNUP_CHALLENGE_TYPE,
                        PUBLIC_EMAIL_SIGNUP_CHALLENGE_PURPOSE,
                        "pending",
                    ),
                )
                challenge_row = cursor.fetchone()

                if challenge_row is None:
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED")

                challenge_id = challenge_row[0]
                user_id = challenge_row[1]
                identity_id = challenge_row[2]
                challenge_locked_until_ts_ms = challenge_row[8]
                flow_token_expires_at_ts_ms = challenge_row[9]
                challenge_status = challenge_row[10]
                confirmed_email = challenge_row[11]

                if challenge_status != "pending":
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED")

                if flow_token_expires_at_ts_ms is not None and flow_token_expires_at_ts_ms < now_ts_ms:
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_user_auth_challenges
                        SET
                            invalidated_at_ts_ms = %s,
                            challenge_status = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            now_ts_ms,
                            "invalidated",
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED")

                if challenge_locked_until_ts_ms is not None and challenge_locked_until_ts_ms > now_ts_ms:
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED")

                if challenge_row[5] < now_ts_ms:
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_user_auth_challenges
                        SET
                            challenge_status = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            "expired",
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED")

                if not otp_code_matches_public_email_signup_hash(
                    otp_code=normalized_otp_code,
                    otp_salt=challenge_row[4],
                    expected_hash=challenge_row[3],
                ):
                    updated_attempt_count = challenge_row[6] + 1
                    locked_until_ts_ms = (
                        now_ts_ms + PUBLIC_EMAIL_SIGNUP_LOCKOUT_MS
                        if updated_attempt_count >= challenge_row[7]
                        else None
                    )
                    updated_challenge_status = (
                        "locked"
                        if updated_attempt_count >= challenge_row[7]
                        else "pending"
                    )

                    cursor.execute(
                        """
                        UPDATE stephen_dcx_user_auth_challenges
                        SET
                            attempt_count = %s,
                            last_attempted_at_ts_ms = %s,
                            locked_until_ts_ms = %s,
                            challenge_status = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            updated_attempt_count,
                            now_ts_ms,
                            locked_until_ts_ms,
                            updated_challenge_status,
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED")

                cursor.execute(
                    """
                    UPDATE stephen_dcx_users
                    SET
                        primary_email_confirmed = TRUE,
                        primary_email_confirmed_at_ts_ms = %s,
                        account_status = %s,
                        last_seen_at_ts_ms = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (
                        now_ts_ms,
                        "confirmed",
                        now_ts_ms,
                        now_ts_ms,
                        user_id,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_user_auth_identities
                    SET
                        provider_email_confirmed = TRUE,
                        last_authenticated_at_ts_ms = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (
                        now_ts_ms,
                        now_ts_ms,
                        identity_id,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_user_auth_challenges
                    SET
                        last_attempted_at_ts_ms = %s,
                        consumed_at_ts_ms = %s,
                        challenge_status = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (
                        now_ts_ms,
                        now_ts_ms,
                        "consumed",
                        now_ts_ms,
                        challenge_id,
                    ),
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFY_PERSISTENCE_FAILED") from exc

    return {
        "status": "confirmed",
        "confirmed_email": confirmed_email,
        "language_code": normalized_language_code,
        "verification_page_url": normalized_verification_page_url,
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
