"""
CONTEXT:
This file creates or refreshes the persisted backend artifacts for the DCX public email-signup flow.
It exists so the `/users/signup-email` route can translate one validated public request into
durable user, identity, challenge, and opaque browser flow-token state before the delivery
provider is called.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

import psycopg2

from users.signup_email.accept_public_email_signup_request import (
    accept_public_email_signup_request_capability,
)
from users.signup_email.public_email_signup_otp_support import (
    PUBLIC_EMAIL_SIGNUP_CHALLENGE_PURPOSE,
    PUBLIC_EMAIL_SIGNUP_CHALLENGE_TYPE,
    PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_LIFETIME_MS,
    PUBLIC_EMAIL_SIGNUP_MAX_SENDS_PER_WINDOW,
    PUBLIC_EMAIL_SIGNUP_MAX_VERIFY_ATTEMPTS,
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
)
from storage.db_config import DB_CONFIG


def create_or_refresh_public_email_signup_artifacts_capability(
    email: str,
    language_code: str,
    signup_page_url: str,
    origin_header: str | None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    user_uuid_provider: Callable[[], uuid.UUID] | None = None,
    otp_code_provider: Callable[[], str] | None = None,
    otp_salt_provider: Callable[[], str] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email, language_code, signup_page_url, and origin_header describe one public signup request.
        - The configured database is reachable and the user-signup schema has been applied.
      postconditions:
        - Ensures one durable user row exists for the normalized email.
        - Ensures one durable email auth identity row exists for that user.
        - Ensures one active pending email-signup challenge row exists for that identity.
        - Returns one stable opaque signup flow token for the active challenge.
        - Preserves the existing email-link resume token when the cooldown blocks a fresh send.
        - Generates one OTP email draft only when a fresh send is allowed.
      side_effects:
        - writes to stephen_dcx_users
        - writes to stephen_dcx_user_auth_identities
        - writes to stephen_dcx_user_auth_challenges
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: public_email_signup:{normalized_email}
      locks:
        - postgres transaction-scoped advisory lock on normalized email
        - row lock on the active challenge row when it exists
      contention_strategy: serialize concurrent signups for the same normalized email, then reuse or refresh one shared active challenge row

    NARRATIVE:
      WHY this exists:
        - The public signup boundary needs a secure persisted state machine before it can hand off into OTP verification.
      WHEN TO USE it:
        - Use it from `/users/signup-email` after route-level origin and rate-limit checks.
      WHEN NOT TO USE it:
        - Do not use it for OTP verification or resend requests.
      WHAT CAN GO WRONG:
        - DB connectivity or schema drift can break the transaction.
        - Duplicate concurrent signups can collide if the advisory lock or unique challenge invariant is removed.
      WHAT COMES NEXT:
        - The route decides whether to call the provider send capability based on `send_required`.
        - The browser can redirect immediately only when a fresh signup flow token was returned.

    TESTS:
      - creates_new_user_identity_and_pending_challenge_for_new_email
      - repeated_signup_within_cooldown_reuses_active_challenge_without_fresh_send
      - returns_signup_flow_token_and_minimal_internal_delivery_state
      - cooldown_reuses_existing_email_link_without_rotating_token
      - confirmed_email_still_returns_a_flow_token
      - send_budget_exceeded_rejects_fresh_send

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_PERSISTENCE_FAILED:
          suggested_action: Confirm database health and schema readiness before retrying signup.
          common_causes:
            - database unavailable
            - schema migration missing
            - transaction failure
          recovery_steps:
            - Re-check the configured database.
            - Reapply the schema if needed.
            - Retry the request.
          retry_safe: true
          what_changed: unknown until the transaction outcome is inspected
          rollback_needed: false
          rollback_operation: rely on the transaction rollback; inspect manually only if a partial committed write is suspected

    CODE:
    """
    normalized_payload = accept_public_email_signup_request_capability(
        email=email,
        language_code=language_code,
        signup_page_url=signup_page_url,
        origin_header=origin_header,
    )
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()
    normalized_email = normalized_payload["normalized_email"]
    normalized_language_code = normalized_payload["language_code"]
    normalized_signup_page_url = normalized_payload["signup_page_url"]
    public_origin = normalized_signup_page_url.split("/", 3)[:3]
    normalized_public_origin = "/".join(public_origin)
    generated_user_uuid = str((user_uuid_provider or uuid.uuid4)())
    raw_signup_flow_token: str | None = None
    signup_flow_token_hash: str | None = None
    signup_flow_token_expires_at_ts_ms: int | None = None

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (normalized_email,),
                )

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_languages
                    WHERE language_code = %s
                      AND is_active = TRUE
                    LIMIT 1
                    """,
                    (normalized_language_code,),
                )
                language_row = cursor.fetchone()
                preferred_language_id = language_row[0] if language_row is not None else None

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_users (
                        user_uuid,
                        primary_email,
                        preferred_language_id,
                        account_status,
                        last_seen_at_ts_ms,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (primary_email) DO UPDATE
                    SET
                        preferred_language_id = COALESCE(EXCLUDED.preferred_language_id, stephen_dcx_users.preferred_language_id),
                        last_seen_at_ts_ms = EXCLUDED.last_seen_at_ts_ms,
                        updated_at_ts_ms = EXCLUDED.updated_at_ts_ms
                    RETURNING
                        id,
                        primary_email_confirmed,
                        account_status
                    """,
                    (
                        generated_user_uuid,
                        normalized_email,
                        preferred_language_id,
                        "pending_email_verification",
                        now_ts_ms,
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                user_row = cursor.fetchone()

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_user_auth_identities (
                        user_id,
                        provider_type,
                        provider_subject,
                        provider_email,
                        provider_email_confirmed,
                        is_primary_identity,
                        is_login_enabled,
                        linked_at_ts_ms,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider_type, provider_subject) DO UPDATE
                    SET
                        user_id = EXCLUDED.user_id,
                        provider_email = EXCLUDED.provider_email,
                        provider_email_confirmed = EXCLUDED.provider_email_confirmed,
                        updated_at_ts_ms = EXCLUDED.updated_at_ts_ms
                    RETURNING id
                    """,
                    (
                        user_row[0],
                        "email",
                        normalized_email,
                        normalized_email,
                        False,
                        True,
                        True,
                        now_ts_ms,
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                identity_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT
                        id,
                        delivery_target,
                        otp_hash,
                        otp_salt,
                        expires_at_ts_ms,
                        sent_at_ts_ms,
                        last_attempted_at_ts_ms,
                        attempt_count,
                        max_attempt_count,
                        resend_count,
                        send_count,
                        next_send_allowed_at_ts_ms,
                        locked_until_ts_ms,
                        public_signup_flow_token_hash,
                        public_signup_flow_token_expires_at_ts_ms,
                        send_budget_window_started_at_ts_ms,
                        send_budget_request_count
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
                        identity_row[0],
                        PUBLIC_EMAIL_SIGNUP_CHALLENGE_TYPE,
                        PUBLIC_EMAIL_SIGNUP_CHALLENGE_PURPOSE,
                        "pending",
                    ),
                )
                active_challenge_row = cursor.fetchone()

                send_required = True
                email_delivery_draft = None
                challenge_id: int
                delivery_failure_recovery_state: dict[str, str | int | None]

                if active_challenge_row is None:
                    signup_flow_token_expires_at_ts_ms = now_ts_ms + PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_LIFETIME_MS
                    send_budget_window_started_at_ts_ms, send_budget_request_count = _build_next_send_budget_window_state(
                        prior_window_started_at_ts_ms=None,
                        prior_window_request_count=0,
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
                    challenge_expires_at_ts_ms = now_ts_ms + PUBLIC_EMAIL_SIGNUP_OTP_LIFETIME_MS
                    next_send_allowed_at_ts_ms = now_ts_ms + PUBLIC_EMAIL_SIGNUP_SEND_COOLDOWN_MS

                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_user_auth_challenges (
                            user_id,
                            user_auth_identity_id,
                            challenge_type,
                            challenge_purpose,
                            delivery_target,
                            otp_hash,
                            otp_salt,
                            expires_at_ts_ms,
                            sent_at_ts_ms,
                            attempt_count,
                            max_attempt_count,
                            resend_count,
                            send_count,
                            send_budget_window_started_at_ts_ms,
                            send_budget_request_count,
                            next_send_allowed_at_ts_ms,
                            locked_until_ts_ms,
                            public_signup_flow_token_hash,
                            public_signup_flow_token_expires_at_ts_ms,
                            challenge_status,
                            created_at_ts_ms,
                            updated_at_ts_ms
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            user_row[0],
                            identity_row[0],
                            PUBLIC_EMAIL_SIGNUP_CHALLENGE_TYPE,
                            PUBLIC_EMAIL_SIGNUP_CHALLENGE_PURPOSE,
                            normalized_email,
                            otp_hash,
                            otp_salt,
                            challenge_expires_at_ts_ms,
                            now_ts_ms,
                            0,
                            PUBLIC_EMAIL_SIGNUP_MAX_VERIFY_ATTEMPTS,
                            0,
                            1,
                            send_budget_window_started_at_ts_ms,
                            send_budget_request_count,
                            next_send_allowed_at_ts_ms,
                            None,
                            signup_flow_token_hash,
                            signup_flow_token_expires_at_ts_ms,
                            "pending",
                            now_ts_ms,
                            now_ts_ms,
                        ),
                    )
                    challenge_id = cursor.fetchone()[0]
                    delivery_failure_recovery_state = {"challenge_id": challenge_id, "recovery_action": "delete_new_challenge"}
                    raw_signup_flow_token = build_public_email_signup_flow_token(
                        challenge_id=challenge_id,
                        flow_token_expires_at_ts_ms=signup_flow_token_expires_at_ts_ms,
                    )
                    signup_flow_token_hash = hash_public_email_signup_flow_token(raw_signup_flow_token)
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_user_auth_challenges
                        SET
                            public_signup_flow_token_hash = %s,
                            public_signup_flow_token_expires_at_ts_ms = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            signup_flow_token_hash,
                            signup_flow_token_expires_at_ts_ms,
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
                    verification_link_url = build_public_email_signup_verification_link_url(
                        public_origin=normalized_public_origin,
                        language_code=normalized_language_code,
                        signup_flow_token=raw_signup_flow_token,
                    )
                    email_delivery_draft = build_public_email_signup_otp_email_delivery_draft(
                        language_code=normalized_language_code,
                        normalized_email=normalized_email,
                        otp_code=otp_code,
                        verification_link_url=verification_link_url,
                    )
                else:
                    challenge_id = active_challenge_row[0]
                    send_count = active_challenge_row[10] or 0
                    resend_count = active_challenge_row[9] or 0
                    prior_sent_at_ts_ms = active_challenge_row[5]
                    next_send_allowed_at_ts_ms = active_challenge_row[11]
                    delivery_failure_recovery_state = {
                        "challenge_id": challenge_id,
                        "recovery_action": "restore_existing_challenge_state",
                        "prior_delivery_target": active_challenge_row[1],
                        "prior_otp_hash": active_challenge_row[2],
                        "prior_otp_salt": active_challenge_row[3],
                        "prior_expires_at_ts_ms": active_challenge_row[4],
                        "prior_sent_at_ts_ms": prior_sent_at_ts_ms,
                        "prior_last_attempted_at_ts_ms": active_challenge_row[6],
                        "prior_attempt_count": active_challenge_row[7],
                        "prior_max_attempt_count": active_challenge_row[8],
                        "prior_resend_count": resend_count,
                        "prior_send_count": send_count,
                        "prior_next_send_allowed_at_ts_ms": next_send_allowed_at_ts_ms,
                        "prior_locked_until_ts_ms": active_challenge_row[12],
                        "prior_public_signup_flow_token_hash": active_challenge_row[13],
                        "prior_public_signup_flow_token_expires_at_ts_ms": active_challenge_row[14],
                        "prior_send_budget_window_started_at_ts_ms": active_challenge_row[15],
                        "prior_send_budget_request_count": active_challenge_row[16] or 0,
                    }
                    signup_flow_token_expires_at_ts_ms = active_challenge_row[14] or (
                        now_ts_ms + PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_LIFETIME_MS
                    )
                    raw_signup_flow_token = build_public_email_signup_flow_token(
                        challenge_id=challenge_id,
                        flow_token_expires_at_ts_ms=signup_flow_token_expires_at_ts_ms,
                    )
                    if active_challenge_row[14] is None:
                        signup_flow_token_hash = hash_public_email_signup_flow_token(raw_signup_flow_token)
                        cursor.execute(
                            """
                            UPDATE stephen_dcx_user_auth_challenges
                            SET
                                public_signup_flow_token_hash = %s,
                                public_signup_flow_token_expires_at_ts_ms = %s,
                                updated_at_ts_ms = %s
                            WHERE id = %s
                            """,
                            (
                                signup_flow_token_hash,
                                signup_flow_token_expires_at_ts_ms,
                                now_ts_ms,
                                challenge_id,
                            ),
                        )

                    if next_send_allowed_at_ts_ms is not None and now_ts_ms < next_send_allowed_at_ts_ms:
                        send_required = False
                    else:
                        signup_flow_token_expires_at_ts_ms = now_ts_ms + PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_LIFETIME_MS
                        send_budget_window_started_at_ts_ms, send_budget_request_count = _build_next_send_budget_window_state(
                            prior_window_started_at_ts_ms=active_challenge_row[15],
                            prior_window_request_count=active_challenge_row[16] or 0,
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
                        raw_signup_flow_token = build_public_email_signup_flow_token(
                            challenge_id=challenge_id,
                            flow_token_expires_at_ts_ms=signup_flow_token_expires_at_ts_ms,
                        )
                        signup_flow_token_hash = hash_public_email_signup_flow_token(raw_signup_flow_token)
                        challenge_expires_at_ts_ms = now_ts_ms + PUBLIC_EMAIL_SIGNUP_OTP_LIFETIME_MS
                        next_send_allowed_at_ts_ms = now_ts_ms + PUBLIC_EMAIL_SIGNUP_SEND_COOLDOWN_MS
                        cursor.execute(
                            """
                            UPDATE stephen_dcx_user_auth_challenges
                            SET
                                delivery_target = %s,
                                otp_hash = %s,
                                otp_salt = %s,
                                expires_at_ts_ms = %s,
                                sent_at_ts_ms = %s,
                                last_attempted_at_ts_ms = NULL,
                                attempt_count = %s,
                                max_attempt_count = %s,
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
                                normalized_email,
                                otp_hash,
                                otp_salt,
                                challenge_expires_at_ts_ms,
                                now_ts_ms,
                                0,
                                PUBLIC_EMAIL_SIGNUP_MAX_VERIFY_ATTEMPTS,
                                send_count + 1,
                                send_budget_window_started_at_ts_ms,
                                send_budget_request_count,
                                next_send_allowed_at_ts_ms,
                                None,
                                signup_flow_token_hash,
                                signup_flow_token_expires_at_ts_ms,
                                "pending",
                                now_ts_ms,
                                challenge_id,
                            ),
                        )
                        verification_link_url = build_public_email_signup_verification_link_url(
                            public_origin=normalized_public_origin,
                            language_code=normalized_language_code,
                            signup_flow_token=raw_signup_flow_token,
                        )
                        email_delivery_draft = build_public_email_signup_otp_email_delivery_draft(
                            language_code=normalized_language_code,
                            normalized_email=normalized_email,
                            otp_code=otp_code,
                            verification_link_url=verification_link_url,
                        )

                return {
                    "signup_flow_token": raw_signup_flow_token,
                    "send_required": send_required,
                    "challenge_id": challenge_id,
                    "email_delivery_draft": email_delivery_draft,
                    "delivery_failure_recovery_state": delivery_failure_recovery_state,
                }
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_PERSISTENCE_FAILED") from exc


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)


def _build_next_send_budget_window_state(
    prior_window_started_at_ts_ms: int | None,
    prior_window_request_count: int,
    now_ts_ms: int,
) -> tuple[int, int]:
    """Minimal contract: return the active fixed-window send budget state after one new send attempt."""
    if (
        prior_window_started_at_ts_ms is None
        or now_ts_ms - prior_window_started_at_ts_ms >= PUBLIC_EMAIL_SIGNUP_SEND_BUDGET_WINDOW_MS
    ):
        return now_ts_ms, 1

    return prior_window_started_at_ts_ms, prior_window_request_count + 1
