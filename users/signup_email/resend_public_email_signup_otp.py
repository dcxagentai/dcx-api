"""
CONTEXT:
This file refreshes the public DCX email-signup OTP using the opaque signup flow token.
It exists so the browser can request a fresh code without resubmitting the email address
or leaking identity state through the URL.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from users.signup_email.public_email_signup_otp_support import (
    PUBLIC_EMAIL_SIGNUP_ALLOWED_VERIFY_PATHS,
    PUBLIC_EMAIL_SIGNUP_CHALLENGE_PURPOSE,
    PUBLIC_EMAIL_SIGNUP_CHALLENGE_TYPE,
    PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_LIFETIME_MS,
    PUBLIC_EMAIL_SIGNUP_MAX_VERIFY_ATTEMPTS,
    PUBLIC_EMAIL_SIGNUP_MAX_SENDS_PER_WINDOW,
    PUBLIC_EMAIL_SIGNUP_OTP_LIFETIME_MS,
    PUBLIC_EMAIL_SIGNUP_SEND_BUDGET_WINDOW_MS,
    PUBLIC_EMAIL_SIGNUP_SEND_COOLDOWN_MS,
    build_public_email_signup_flow_token,
    build_public_email_signup_otp_email_delivery_draft,
    build_public_email_signup_verification_link_url,
    generate_public_email_signup_otp_code,
    generate_public_email_signup_otp_salt,
    hash_public_email_signup_flow_token,
    hash_public_email_signup_otp_code,
    normalize_public_email_signup_flow_token,
    normalize_public_email_signup_language_code,
    normalize_public_email_signup_origin_header,
    normalize_public_email_signup_page_url,
)
from storage.db_config import DB_CONFIG


def resend_public_email_signup_otp_capability(
    signup_flow_token: str,
    language_code: str,
    resend_page_url: str,
    origin_header: str | None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    otp_code_provider: Callable[[], str] | None = None,
    otp_salt_provider: Callable[[], str] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - signup_flow_token, language_code, resend_page_url, and origin_header describe one public resend request.
        - The configured database is reachable and the user-signup schema has been applied.
      postconditions:
        - Refreshes the active pending email-signup challenge when the cooldown allows it.
        - Issues one fresh opaque flow token for the browser.
        - Generates one new OTP email draft for provider delivery.
      side_effects:
        - writes to stephen_dcx_user_auth_challenges
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: public_email_signup_otp_resend:{signup_flow_token_hash}
      locks:
        - row lock on the active challenge row found through the flow token hash
      contention_strategy: serialize resend operations on the active challenge row, then enforce cooldown using persisted timestamps

    NARRATIVE:
      WHY this exists:
        - Users need one recovery path for expired or lost OTP emails without restarting the entire browser journey every time.
      WHEN TO USE it:
        - Use it from `/users/signup-email/resend-otp`.
      WHEN NOT TO USE it:
        - Do not use it for initial signup requests.
      WHAT CAN GO WRONG:
        - The token can be stale.
        - The active challenge can be missing or already consumed.
        - The resend cooldown can still be active.
      WHAT COMES NEXT:
        - The route calls the provider send capability with the returned draft only when resend is allowed.

    TESTS:
      - resend_refreshes_existing_challenge_and_rotates_flow_token
      - resend_rejects_cooldown_window
      - resend_requires_restart_when_flow_token_missing

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_INVALID:
          suggested_action: Restart the signup flow from the public landing page.
          common_causes:
            - missing or malformed browser flow token
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
      - API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED:
          suggested_action: Restart the signup flow from the public landing page.
          common_causes:
            - stale or consumed token
            - missing active challenge
          recovery_steps:
            - Return to the signup page.
            - Submit the email again.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_OTP_RESEND_COOLDOWN_ACTIVE:
          suggested_action: Wait a little before requesting another code.
          common_causes:
            - resend requested inside the active cooldown window
          recovery_steps:
            - Pause briefly.
            - Retry resend later.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_OTP_RESEND_PERSISTENCE_FAILED:
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
    normalized_resend_page_url = normalize_public_email_signup_page_url(
        page_url=resend_page_url,
        expected_origin=normalized_origin,
        allowed_paths=PUBLIC_EMAIL_SIGNUP_ALLOWED_VERIFY_PATHS,
        invalid_error_code="API_PUBLIC_EMAIL_SIGNUP_PAGE_URL_INVALID",
    )
    normalized_flow_token = normalize_public_email_signup_flow_token(
        flow_token=signup_flow_token,
        invalid_error_code="API_PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_INVALID",
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
                        delivery_target,
                        otp_hash,
                        otp_salt,
                        expires_at_ts_ms,
                        resend_count,
                        send_count,
                        sent_at_ts_ms,
                        last_attempted_at_ts_ms,
                        attempt_count,
                        max_attempt_count,
                        next_send_allowed_at_ts_ms,
                        locked_until_ts_ms,
                        public_signup_flow_token_hash,
                        public_signup_flow_token_expires_at_ts_ms,
                        send_budget_window_started_at_ts_ms,
                        send_budget_request_count,
                        challenge_status
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

                if challenge_row[16] is not None and challenge_row[16] < now_ts_ms:
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
                            challenge_row[0],
                        ),
                    )
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED")

                next_send_allowed_at_ts_ms = challenge_row[13]

                if next_send_allowed_at_ts_ms is not None and now_ts_ms < next_send_allowed_at_ts_ms:
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_OTP_RESEND_COOLDOWN_ACTIVE")

                send_budget_window_started_at_ts_ms, send_budget_request_count = _build_next_send_budget_window_state(
                    prior_window_started_at_ts_ms=challenge_row[17],
                    prior_window_request_count=challenge_row[18] or 0,
                    now_ts_ms=now_ts_ms,
                )
                if send_budget_request_count > PUBLIC_EMAIL_SIGNUP_MAX_SENDS_PER_WINDOW:
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_SEND_LIMIT_REACHED")

                otp_code = (otp_code_provider or generate_public_email_signup_otp_code)()
                otp_salt = (otp_salt_provider or generate_public_email_signup_otp_salt)()
                otp_hash = hash_public_email_signup_otp_code(
                    otp_code=otp_code,
                    otp_salt=otp_salt,
                )
                next_signup_flow_token_expires_at_ts_ms = now_ts_ms + PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_LIFETIME_MS
                raw_signup_flow_token = build_public_email_signup_flow_token(
                    challenge_id=challenge_row[0],
                    flow_token_expires_at_ts_ms=next_signup_flow_token_expires_at_ts_ms,
                )
                next_signup_flow_token_hash = hash_public_email_signup_flow_token(raw_signup_flow_token)

                cursor.execute(
                    """
                    UPDATE stephen_dcx_user_auth_challenges
                    SET
                        otp_hash = %s,
                        otp_salt = %s,
                        expires_at_ts_ms = %s,
                        sent_at_ts_ms = %s,
                        last_attempted_at_ts_ms = NULL,
                        attempt_count = %s,
                        max_attempt_count = %s,
                        resend_count = %s,
                        send_count = %s,
                        send_budget_window_started_at_ts_ms = %s,
                        send_budget_request_count = %s,
                        next_send_allowed_at_ts_ms = %s,
                        locked_until_ts_ms = %s,
                        public_signup_flow_token_hash = %s,
                        public_signup_flow_token_expires_at_ts_ms = %s,
                        challenge_status = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (
                        otp_hash,
                        otp_salt,
                        now_ts_ms + PUBLIC_EMAIL_SIGNUP_OTP_LIFETIME_MS,
                        now_ts_ms,
                        0,
                        PUBLIC_EMAIL_SIGNUP_MAX_VERIFY_ATTEMPTS,
                        (challenge_row[7] or 0) + 1,
                        (challenge_row[8] or 0) + 1,
                        send_budget_window_started_at_ts_ms,
                        send_budget_request_count,
                        now_ts_ms + PUBLIC_EMAIL_SIGNUP_SEND_COOLDOWN_MS,
                        None,
                        next_signup_flow_token_hash,
                        next_signup_flow_token_expires_at_ts_ms,
                        "pending",
                        now_ts_ms,
                        challenge_row[0],
                    ),
                )
                normalized_public_origin = normalized_resend_page_url.split("/", 3)[:3]
                verification_link_url = build_public_email_signup_verification_link_url(
                    public_origin="/".join(normalized_public_origin),
                    language_code=normalized_language_code,
                    signup_flow_token=raw_signup_flow_token,
                )
                email_delivery_draft = build_public_email_signup_otp_email_delivery_draft(
                    language_code=normalized_language_code,
                    normalized_email=challenge_row[3],
                    otp_code=otp_code,
                    verification_link_url=verification_link_url,
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_OTP_RESEND_PERSISTENCE_FAILED") from exc

    return {
        "status": "otp_resent",
        "signup_flow_token": raw_signup_flow_token,
        "challenge_id": challenge_row[0],
        "email_delivery_draft": email_delivery_draft,
        "delivery_failure_recovery_state": {
            "challenge_id": challenge_row[0],
            "recovery_action": "restore_existing_challenge_state",
            "prior_delivery_target": challenge_row[3],
            "prior_otp_hash": challenge_row[4],
            "prior_otp_salt": challenge_row[5],
            "prior_expires_at_ts_ms": challenge_row[6],
            "prior_resend_count": challenge_row[7] or 0,
            "prior_send_count": challenge_row[8] or 0,
            "prior_sent_at_ts_ms": challenge_row[9],
            "prior_last_attempted_at_ts_ms": challenge_row[10],
            "prior_attempt_count": challenge_row[11],
            "prior_max_attempt_count": challenge_row[12],
            "prior_next_send_allowed_at_ts_ms": challenge_row[13],
            "prior_locked_until_ts_ms": challenge_row[14],
            "prior_public_signup_flow_token_hash": challenge_row[15],
            "prior_public_signup_flow_token_expires_at_ts_ms": challenge_row[16],
            "prior_send_budget_window_started_at_ts_ms": challenge_row[17],
            "prior_send_budget_request_count": challenge_row[18] or 0,
        },
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)


def _build_next_send_budget_window_state(
    prior_window_started_at_ts_ms: int | None,
    prior_window_request_count: int,
    now_ts_ms: int,
) -> tuple[int, int]:
    """Minimal contract: return the active fixed-window send budget state after one new resend attempt."""
    if (
        prior_window_started_at_ts_ms is None
        or now_ts_ms - prior_window_started_at_ts_ms >= PUBLIC_EMAIL_SIGNUP_SEND_BUDGET_WINDOW_MS
    ):
        return now_ts_ms, 1

    return prior_window_started_at_ts_ms, prior_window_request_count + 1
