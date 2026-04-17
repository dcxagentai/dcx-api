"""
CONTEXT:
This file prepares one pending WhatsApp verification-link challenge for linking a phone number to
an already authenticated DCX account.
It exists so the app can start phone verification without writing an unverified phone number into
the user's live confirmed profile fields and without requiring copy-paste OTP entry.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG
from users.account_phone.dcx_whatsapp_phone_link_challenge_support import (
    DCX_WHATSAPP_PHONE_LINK_CHANNEL,
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
    DCX_WHATSAPP_PHONE_LINK_MAX_SENDS_PER_WINDOW,
    DCX_WHATSAPP_PHONE_LINK_SEND_BUDGET_WINDOW_MS,
    DCX_WHATSAPP_PHONE_LINK_TOKEN_LIFETIME_MS,
    build_dcx_whatsapp_phone_link_challenge_token,
    build_dcx_whatsapp_phone_link_verification_page_suffix,
    build_dcx_whatsapp_phone_link_verification_page_url,
    hash_dcx_whatsapp_phone_link_challenge_token,
    normalize_dcx_whatsapp_phone_link_phone_e164,
)

logger = logging.getLogger("uvicorn.error")


def prepare_authenticated_dcx_user_whatsapp_phone_link_delivery(
    authenticated_user_id: int,
    candidate_phone_number: str,
    language_code: str | None = None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    raw_token_provider: Callable[[], str] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one authenticated DCX user.
        - candidate_phone_number is one user-entered phone string intended for WhatsApp linking.
        - The configured database is reachable.
      postconditions:
        - Ensures one pending WhatsApp phone-link challenge exists for the user.
        - Does not write the phone into the user's confirmed profile fields yet.
        - Returns the raw verification-link token and ready-to-send app suffix unless the phone is already confirmed for this user.
      side_effects:
        - writes to stephen_dcx_user_auth_challenges
        - may insert or update stephen_dcx_users_contact_methods
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: dcx_whatsapp_phone_link:{authenticated_user_id}
      locks:
        - postgres transaction-scoped advisory lock on user id plus phone-link purpose
        - row lock on the current user row
        - row lock on the existing pending phone-link challenge row when it exists
      contention_strategy: serialize concurrent phone-link requests for one user, then refresh the shared pending challenge row

    NARRATIVE:
      WHY this exists:
        - The first live WhatsApp step should prove phone ownership before the app treats that number as the user's confirmed WhatsApp identity.
      WHEN TO USE it:
        - Use it when an authenticated app user enters or resends a phone-link WhatsApp verification message.
      WHEN NOT TO USE it:
        - Do not use it to verify the clicked link or to process inbound WhatsApp webhooks.
      WHAT CAN GO WRONG:
        - The phone can be malformed or already linked to another user.
        - Cooldown or send-budget rules can block an immediate resend.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The caller sends the secure link through the provider adapter, marks the delivery as sent, and then returns the refreshed account summary.

    TESTS:
      - prepares_new_pending_whatsapp_phone_link_for_valid_phone
      - already_confirmed_whatsapp_phone_returns_without_send
      - raises_when_phone_is_already_linked_to_another_user
      - enforces_send_cooldown_for_active_delivered_challenge

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND:
          suggested_action: Sign in again and retry after confirming the user account still exists.
          common_causes:
            - stale session principal
            - deleted user row
          recovery_steps:
            - Sign in again.
            - Inspect the user row in admin if needed.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_INVALID:
          suggested_action: Re-enter the phone with country code, for example +34600000001.
          common_causes:
            - missing country code
            - invalid phone shape
          recovery_steps:
            - Add the country code.
            - Remove invalid punctuation.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER:
          suggested_action: Use a different phone number or inspect the existing linked account before retrying.
          common_causes:
            - phone already claimed by another user
            - stale phone ownership in the system
          recovery_steps:
            - Confirm which account owns the phone.
            - Retry with the intended number.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_SEND_COOLDOWN_ACTIVE:
          suggested_action: Wait for the resend cooldown to pass, then retry.
          common_causes:
            - repeated resend clicks inside the cooldown window
          recovery_steps:
            - Wait until the cooldown expires.
            - Retry the send.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_SEND_LIMIT_REACHED:
          suggested_action: Wait for the send window to reset before retrying.
          common_causes:
            - too many WhatsApp verification sends in one short window
          recovery_steps:
            - Wait for the send window to expire.
            - Retry later.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_PERSISTENCE_FAILED:
          suggested_action: Confirm database health and retry after the backend is stable.
          common_causes:
            - database unavailable
            - transaction failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true
          what_changed:
            - unknown until the transaction outcome is inspected
          rollback_needed: false
          rollback_operation:
            - rely on transaction rollback and inspect manually only if a partial committed write is suspected

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND")

    normalized_phone_number = normalize_dcx_whatsapp_phone_link_phone_e164(candidate_phone_number)
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()
    raw_phone_link_token = (raw_token_provider or build_dcx_whatsapp_phone_link_challenge_token)()
    phone_link_token_hash = hash_dcx_whatsapp_phone_link_challenge_token(raw_phone_link_token)
    challenge_expires_at_ts_ms = now_ts_ms + DCX_WHATSAPP_PHONE_LINK_TOKEN_LIFETIME_MS
    verification_link_suffix = build_dcx_whatsapp_phone_link_verification_page_suffix(
        raw_phone_link_token=raw_phone_link_token,
        language_code=language_code,
    )
    verification_link_url = build_dcx_whatsapp_phone_link_verification_page_url(
        raw_phone_link_token=raw_phone_link_token,
        language_code=language_code,
    )

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"whatsapp-phone-link:{authenticated_user_id}",),
                )
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_users
                    WHERE id = %s
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (authenticated_user_id,),
                )
                user_row = cursor.fetchone()
                if user_row is None:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT
                        cm.id,
                        cm.is_verified,
                        (
                            SELECT id
                            FROM stephen_dcx_user_auth_identities
                            WHERE user_id = cm.user_id
                              AND contact_method_id = cm.id
                              AND provider_type = %s
                            LIMIT 1
                        ) AS whatsapp_identity_id
                    FROM stephen_dcx_users_contact_methods cm
                    WHERE cm.user_id = %s
                      AND cm.contact_type = %s
                      AND cm.normalized_value = %s
                      AND cm.is_active = TRUE
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        DCX_WHATSAPP_PHONE_LINK_CHANNEL,
                        authenticated_user_id,
                        "phone",
                        normalized_phone_number,
                    ),
                )
                existing_contact_method_row = cursor.fetchone()

                if (
                    existing_contact_method_row is not None
                    and existing_contact_method_row[1] is True
                    and existing_contact_method_row[2] is not None
                ):
                    return {
                        "status": "already_confirmed",
                        "send_required": False,
                        "phone_e164": normalized_phone_number,
                    }

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_users_contact_methods
                    WHERE contact_type = %s
                      AND normalized_value = %s
                      AND is_active = TRUE
                      AND user_id <> %s
                    LIMIT 1
                    """,
                    ("phone", normalized_phone_number, authenticated_user_id),
                )
                if cursor.fetchone() is not None:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_user_auth_identities
                    WHERE provider_type = %s
                      AND provider_subject = %s
                      AND user_id <> %s
                    LIMIT 1
                    """,
                    ("whatsapp", normalized_phone_number, authenticated_user_id),
                )
                if cursor.fetchone() is not None:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER")

                if existing_contact_method_row is None:
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_users_contact_methods (
                            user_id,
                            contact_type,
                            contact_value,
                            normalized_value,
                            display_label,
                            is_primary,
                            is_login_enabled,
                            is_recovery_enabled,
                            is_notification_enabled,
                            is_verified,
                            verified_at_ts_ms,
                            verification_method,
                            is_active,
                            last_used_at_ts_ms,
                            created_at_ts_ms,
                            updated_at_ts_ms
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            authenticated_user_id,
                            "phone",
                            normalized_phone_number,
                            normalized_phone_number,
                            "",
                            False,
                            False,
                            False,
                            False,
                            False,
                            None,
                            None,
                            True,
                            now_ts_ms,
                            now_ts_ms,
                            now_ts_ms,
                        ),
                    )
                    contact_method_id = cursor.fetchone()[0]
                else:
                    contact_method_id = existing_contact_method_row[0]
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_users_contact_methods
                        SET
                            contact_value = %s,
                            last_used_at_ts_ms = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            normalized_phone_number,
                            now_ts_ms,
                            now_ts_ms,
                            contact_method_id,
                        ),
                    )

                cursor.execute(
                    """
                    SELECT
                        id,
                        delivery_target,
                        sent_at_ts_ms,
                        next_send_allowed_at_ts_ms,
                        resend_count,
                        send_count,
                        send_budget_window_started_at_ts_ms,
                        send_budget_request_count
                    FROM stephen_dcx_user_auth_challenges
                    WHERE user_id = %s
                      AND challenge_type = %s
                      AND challenge_purpose = %s
                      AND consumed_at_ts_ms IS NULL
                      AND invalidated_at_ts_ms IS NULL
                    ORDER BY updated_at_ts_ms DESC, id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        authenticated_user_id,
                        DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
                        DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
                    ),
                )
                active_challenge_row = cursor.fetchone()

                if (
                    active_challenge_row is not None
                    and active_challenge_row[2] is not None
                    and active_challenge_row[3] is not None
                    and now_ts_ms < active_challenge_row[3]
                ):
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_SEND_COOLDOWN_ACTIVE")

                send_budget_window_started_at_ts_ms, send_budget_request_count = (
                    _build_next_send_budget_window_state(
                        prior_window_started_at_ts_ms=active_challenge_row[6] if active_challenge_row else None,
                        prior_window_request_count=active_challenge_row[7] if active_challenge_row else 0,
                        now_ts_ms=now_ts_ms,
                    )
                )
                if send_budget_request_count > DCX_WHATSAPP_PHONE_LINK_MAX_SENDS_PER_WINDOW:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_SEND_LIMIT_REACHED")

                if active_challenge_row is None:
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
                            last_attempted_at_ts_ms,
                            attempt_count,
                            max_attempt_count,
                            resend_count,
                            last_resent_at_ts_ms,
                            send_count,
                            send_budget_window_started_at_ts_ms,
                            send_budget_request_count,
                            next_send_allowed_at_ts_ms,
                            locked_until_ts_ms,
                            challenge_status,
                            created_at_ts_ms,
                            updated_at_ts_ms
                        )
                        VALUES (%s, NULL, %s, %s, %s, %s, NULL, %s, NULL, NULL, 0, 1, 0, NULL, 1, %s, %s, NULL, NULL, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            authenticated_user_id,
                            DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
                            DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
                            normalized_phone_number,
                            phone_link_token_hash,
                            challenge_expires_at_ts_ms,
                            send_budget_window_started_at_ts_ms,
                            send_budget_request_count,
                            "pending",
                            now_ts_ms,
                            now_ts_ms,
                        ),
                    )
                    challenge_id = cursor.fetchone()[0]
                else:
                    challenge_id = active_challenge_row[0]
                    resend_count = active_challenge_row[4] or 0
                    send_count = active_challenge_row[5] or 0
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_user_auth_challenges
                        SET
                            user_auth_identity_id = NULL,
                            delivery_target = %s,
                            otp_hash = %s,
                            otp_salt = NULL,
                            expires_at_ts_ms = %s,
                            sent_at_ts_ms = NULL,
                            last_attempted_at_ts_ms = NULL,
                            attempt_count = 0,
                            max_attempt_count = 1,
                            resend_count = %s,
                            last_resent_at_ts_ms = NULL,
                            send_count = %s,
                            send_budget_window_started_at_ts_ms = %s,
                            send_budget_request_count = %s,
                            next_send_allowed_at_ts_ms = NULL,
                            locked_until_ts_ms = NULL,
                            challenge_status = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            normalized_phone_number,
                            phone_link_token_hash,
                            challenge_expires_at_ts_ms,
                            resend_count + 1,
                            send_count + 1,
                            send_budget_window_started_at_ts_ms,
                            send_budget_request_count,
                            "pending",
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        logger.exception(
            "prepare_authenticated_dcx_user_whatsapp_phone_link_delivery_failed "
            "user_id=%s phone_e164=%s",
            authenticated_user_id,
            normalized_phone_number,
        )
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_PERSISTENCE_FAILED") from exc

    return {
        "status": "pending_verification",
        "send_required": True,
        "challenge_id": challenge_id,
        "phone_e164": normalized_phone_number,
        "raw_phone_link_token": raw_phone_link_token,
        "verification_link_suffix": verification_link_suffix,
        "verification_link_url": verification_link_url,
    }


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
        or now_ts_ms - prior_window_started_at_ts_ms >= DCX_WHATSAPP_PHONE_LINK_SEND_BUDGET_WINDOW_MS
    ):
        return now_ts_ms, 1

    return prior_window_started_at_ts_ms, prior_window_request_count + 1
