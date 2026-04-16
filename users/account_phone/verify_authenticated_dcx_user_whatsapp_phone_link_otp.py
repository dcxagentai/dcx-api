"""
CONTEXT:
This file verifies one WhatsApp OTP challenge for linking a phone number to an already
authenticated DCX account.
It exists so the account flow can promote a pending phone number into the user's live
confirmed profile only after the user proves possession of that WhatsApp number.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG
from users.account_phone.dcx_whatsapp_phone_link_otp_support import (
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
    DCX_WHATSAPP_PHONE_LINK_MAX_VERIFY_ATTEMPTS,
    hash_dcx_whatsapp_phone_link_otp_code,
    normalize_dcx_whatsapp_phone_link_otp_code,
)

DCX_WHATSAPP_PHONE_LINK_LOCKOUT_MS = 10 * 60 * 1000


def verify_authenticated_dcx_user_whatsapp_phone_link_otp(
    authenticated_user_id: int,
    candidate_otp_code: str,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one authenticated DCX user.
        - candidate_otp_code is one user-entered six-digit OTP.
        - The configured database is reachable.
      postconditions:
        - Consumes the active delivered WhatsApp phone-link challenge on success.
        - Promotes the verified phone into the user's primary verified phone contact method.
        - Ensures one WhatsApp auth identity row points at the verified E.164 phone.
      side_effects:
        - updates stephen_dcx_user_auth_challenges
        - updates stephen_dcx_users_contact_methods
        - inserts or updates stephen_dcx_user_auth_identities
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: dcx_whatsapp_phone_link_verify:{authenticated_user_id}
      locks:
        - postgres transaction-scoped advisory lock on user id plus phone-link purpose
        - row lock on the active phone-link challenge row
        - row lock on the current user's WhatsApp identity row when it exists
      contention_strategy: serialize concurrent verify attempts for one user, then mutate the shared pending challenge and confirmed phone state atomically

    NARRATIVE:
      WHY this exists:
        - The first production WhatsApp identity bridge should only attach a phone to the account after the code from WhatsApp proves ownership.
      WHEN TO USE it:
        - Use it when the authenticated app user submits the received WhatsApp OTP.
      WHEN NOT TO USE it:
        - Do not use it for public signup OTP verification or password reset.
      WHAT CAN GO WRONG:
        - No active delivered challenge may exist.
        - The OTP can be wrong, expired, or locked out.
        - Another user may have claimed the phone before verification completed.
      WHAT COMES NEXT:
        - The verified phone can now back inbound WhatsApp message routing to this real DCX user.

    TESTS:
      - correct_otp_links_phone_and_consumes_pending_challenge
      - incorrect_otp_increments_attempt_count
      - duplicate_phone_conflict_after_send_is_rejected

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_OTP_INVALID:
          suggested_action: Enter the six-digit WhatsApp code exactly as received.
          common_causes:
            - malformed OTP
            - non-digit characters
          recovery_steps:
            - Re-enter the six-digit code carefully.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_RESTART_REQUIRED:
          suggested_action: Request a new WhatsApp code from the account page, then retry verification.
          common_causes:
            - no active delivered challenge
            - stale browser state
          recovery_steps:
            - Request a fresh code.
            - Retry with the newest code only once.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_EXPIRED:
          suggested_action: Request a new WhatsApp code and retry with the newest code only once.
          common_causes:
            - code expired before verification
          recovery_steps:
            - Request a new code.
            - Enter the newest code promptly.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_LOCKED:
          suggested_action: Wait for the lock window to pass or request a new code later.
          common_causes:
            - too many incorrect OTP attempts
          recovery_steps:
            - Wait for the lock to expire.
            - Retry with a fresh code if needed.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_VERIFICATION_FAILED:
          suggested_action: Re-enter the WhatsApp code carefully or request a new one.
          common_causes:
            - incorrect OTP
          recovery_steps:
            - Retry with the six-digit code from WhatsApp.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER:
          suggested_action: Use a different phone number or inspect the existing linked account before retrying.
          common_causes:
            - another user confirmed the same phone first
          recovery_steps:
            - Confirm which account owns the phone.
            - Retry with the intended number.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_VERIFY_FAILED:
          suggested_action: Confirm database health and retry after the backend is stable.
          common_causes:
            - database unavailable
            - transaction failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_RESTART_REQUIRED")

    normalized_otp_code = normalize_dcx_whatsapp_phone_link_otp_code(candidate_otp_code)
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"whatsapp-phone-link:{authenticated_user_id}",),
                )
                cursor.execute(
                    """
                    SELECT
                        id,
                        delivery_target,
                        otp_hash,
                        otp_salt,
                        expires_at_ts_ms,
                        sent_at_ts_ms,
                        attempt_count,
                        max_attempt_count,
                        locked_until_ts_ms,
                        challenge_status
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
                challenge_row = cursor.fetchone()

                if challenge_row is None or challenge_row[5] is None:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_RESTART_REQUIRED")

                challenge_id = challenge_row[0]
                target_phone_e164 = challenge_row[1]
                stored_otp_hash = challenge_row[2]
                stored_otp_salt = challenge_row[3]
                expires_at_ts_ms = challenge_row[4]
                attempt_count = challenge_row[6] or 0
                max_attempt_count = challenge_row[7] or DCX_WHATSAPP_PHONE_LINK_MAX_VERIFY_ATTEMPTS
                locked_until_ts_ms = challenge_row[8]

                if locked_until_ts_ms is not None and now_ts_ms < locked_until_ts_ms:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_LOCKED")

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
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_EXPIRED")

                provided_otp_hash = hash_dcx_whatsapp_phone_link_otp_code(
                    otp_code=normalized_otp_code,
                    otp_salt=stored_otp_salt,
                )

                if provided_otp_hash != stored_otp_hash:
                    next_attempt_count = attempt_count + 1
                    next_locked_until_ts_ms = None
                    next_challenge_status = "pending"

                    if next_attempt_count >= max_attempt_count:
                        next_locked_until_ts_ms = now_ts_ms + DCX_WHATSAPP_PHONE_LINK_LOCKOUT_MS
                        next_challenge_status = "locked"

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
                            next_attempt_count,
                            now_ts_ms,
                            next_locked_until_ts_ms,
                            next_challenge_status,
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_VERIFICATION_FAILED")

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
                    ("phone", target_phone_e164, authenticated_user_id),
                )
                if cursor.fetchone() is not None:
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
                            "invalidated",
                            now_ts_ms,
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
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
                    ("whatsapp", target_phone_e164, authenticated_user_id),
                )
                if cursor.fetchone() is not None:
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
                            "invalidated",
                            now_ts_ms,
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_users_contact_methods
                    WHERE user_id = %s
                      AND contact_type = %s
                      AND normalized_value = %s
                      AND is_active = TRUE
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        authenticated_user_id,
                        "phone",
                        target_phone_e164,
                    ),
                )
                existing_contact_method_row = cursor.fetchone()

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
                            target_phone_e164,
                            target_phone_e164,
                            "primary",
                            True,
                            False,
                            False,
                            False,
                            True,
                            now_ts_ms,
                            "whatsapp_otp",
                            True,
                            now_ts_ms,
                            now_ts_ms,
                            now_ts_ms,
                        ),
                    )
                    phone_contact_method_id = cursor.fetchone()[0]
                else:
                    phone_contact_method_id = existing_contact_method_row[0]
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_users_contact_methods
                        SET
                            is_primary = FALSE,
                            updated_at_ts_ms = %s
                        WHERE user_id = %s
                          AND contact_type = %s
                          AND is_primary = TRUE
                          AND is_active = TRUE
                          AND id <> %s
                        """,
                        (
                            now_ts_ms,
                            authenticated_user_id,
                            "phone",
                            phone_contact_method_id,
                        ),
                    )
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_users_contact_methods
                        SET
                            contact_value = %s,
                            display_label = %s,
                            is_primary = TRUE,
                            is_verified = TRUE,
                            verified_at_ts_ms = COALESCE(verified_at_ts_ms, %s),
                            verification_method = COALESCE(verification_method, %s),
                            is_active = TRUE,
                            last_used_at_ts_ms = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            target_phone_e164,
                            "primary",
                            now_ts_ms,
                            "whatsapp_otp",
                            now_ts_ms,
                            now_ts_ms,
                            phone_contact_method_id,
                        ),
                    )

                if existing_contact_method_row is None:
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_users_contact_methods
                        SET
                            is_primary = FALSE,
                            updated_at_ts_ms = %s
                        WHERE user_id = %s
                          AND contact_type = %s
                          AND is_primary = TRUE
                          AND is_active = TRUE
                          AND id <> %s
                        """,
                        (
                            now_ts_ms,
                            authenticated_user_id,
                            "phone",
                            phone_contact_method_id,
                        ),
                    )

                cursor.execute(
                    """
                    SELECT id, provider_subject
                    FROM stephen_dcx_user_auth_identities
                    WHERE user_id = %s
                      AND provider_type = %s
                    ORDER BY id ASC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (authenticated_user_id, "whatsapp"),
                )
                existing_identity_row = cursor.fetchone()

                if existing_identity_row is None:
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_user_auth_identities (
                            user_id,
                            provider_type,
                            provider_subject,
                            is_primary_identity,
                            is_login_enabled,
                            linked_at_ts_ms,
                            created_at_ts_ms,
                            updated_at_ts_ms,
                            contact_method_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            authenticated_user_id,
                            "whatsapp",
                            target_phone_e164,
                            False,
                            False,
                            now_ts_ms,
                            now_ts_ms,
                            now_ts_ms,
                            phone_contact_method_id,
                        ),
                    )
                    whatsapp_identity_id = cursor.fetchone()[0]
                else:
                    whatsapp_identity_id = existing_identity_row[0]
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_user_auth_identities
                        SET
                            provider_subject = %s,
                            is_primary_identity = %s,
                            is_login_enabled = %s,
                            linked_at_ts_ms = %s,
                            updated_at_ts_ms = %s,
                            contact_method_id = %s
                        WHERE id = %s
                        """,
                        (
                            target_phone_e164,
                            False,
                            False,
                            now_ts_ms,
                            now_ts_ms,
                            phone_contact_method_id,
                            whatsapp_identity_id,
                        ),
                    )

                cursor.execute(
                    """
                    UPDATE stephen_dcx_user_auth_challenges
                    SET
                        user_auth_identity_id = %s,
                        consumed_at_ts_ms = %s,
                        challenge_status = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (
                        whatsapp_identity_id,
                        now_ts_ms,
                        "verified",
                        now_ts_ms,
                        challenge_id,
                    ),
                )

                return {
                    "status": "verified",
                    "phone_e164": target_phone_e164,
                    "whatsapp_identity_id": whatsapp_identity_id,
                }
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_VERIFY_FAILED") from exc


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
