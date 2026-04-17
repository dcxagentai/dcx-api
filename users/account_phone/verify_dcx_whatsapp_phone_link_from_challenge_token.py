"""
CONTEXT:
This file verifies one WhatsApp phone-link challenge token and links the phone number to the
target DCX account.
It exists so a WhatsApp button click can prove phone ownership without requiring a logged-in
browser session or copy-paste OTP entry.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG
from users.account_phone.dcx_whatsapp_phone_link_challenge_support import (
    DCX_WHATSAPP_PHONE_LINK_CHANNEL,
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
    hash_dcx_whatsapp_phone_link_challenge_token,
    normalize_dcx_whatsapp_phone_link_challenge_token,
)


def verify_dcx_whatsapp_phone_link_from_challenge_token(
    raw_phone_link_token: str,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - raw_phone_link_token is the browser token captured from one WhatsApp verification link.
        - The configured database is reachable.
      postconditions:
        - Consumes the active delivered WhatsApp phone-link challenge on success.
        - Marks the phone contact method verified for the user.
        - Keeps the existing primary phone unchanged unless no primary phone exists yet.
        - Ensures one WhatsApp auth identity row points at the verified E.164 phone.
      side_effects:
        - updates stephen_dcx_user_auth_challenges
        - updates stephen_dcx_users_contact_methods
        - inserts or updates stephen_dcx_user_auth_identities
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: dcx_whatsapp_phone_link_verify:{token_hash}
      locks:
        - row lock on the active phone-link challenge row
        - row lock on the current user's WhatsApp identity row when it exists
      contention_strategy: serialize concurrent verify attempts for one challenge token, then mutate the shared pending challenge and confirmed phone state atomically

    NARRATIVE:
      WHY this exists:
        - The first production WhatsApp identity bridge should only attach a phone to the account after the secure link from WhatsApp proves ownership.
      WHEN TO USE it:
        - Use it when the app-side verification page posts one captured fragment token back to the API.
      WHEN NOT TO USE it:
        - Do not use it for signup OTP verification or password reset.
      WHAT CAN GO WRONG:
        - No active delivered challenge may exist.
        - The token can be wrong or expired.
        - Another user may have claimed the phone before verification completed.
      WHAT COMES NEXT:
        - The verified phone can now back inbound WhatsApp message routing to this real DCX user.
        - If the user wants this verified phone to become primary later, that should happen through one explicit primary-selection action.

    TESTS:
      - correct_token_links_phone_and_consumes_pending_challenge
      - invalid_token_is_rejected_before_database_work
      - duplicate_phone_conflict_after_send_is_rejected

    ERRORS:
      - API_DCX_WHATSAPP_PHONE_LINK_TOKEN_INVALID:
          suggested_action: Use the newest WhatsApp verification link or request another one from the account page.
          common_causes:
            - malformed token
            - unknown token
          recovery_steps:
            - Reopen the newest message.
            - Request another verification link if needed.
          retry_safe: true
      - API_DCX_WHATSAPP_PHONE_LINK_TOKEN_EXPIRED:
          suggested_action: Request a new WhatsApp verification link from the account page.
          common_causes:
            - token expired before use
          recovery_steps:
            - Start the phone verification flow again.
          retry_safe: true
      - API_DCX_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER:
          suggested_action: Use a different phone number or inspect the existing linked account before retrying.
          common_causes:
            - another user confirmed the same phone first
          recovery_steps:
            - Confirm which account owns the phone.
            - Retry with the intended number.
          retry_safe: true
      - API_DCX_WHATSAPP_PHONE_LINK_VERIFY_FAILED:
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
    normalized_phone_link_token = normalize_dcx_whatsapp_phone_link_challenge_token(
        raw_phone_link_token
    )
    phone_link_token_hash = hash_dcx_whatsapp_phone_link_challenge_token(normalized_phone_link_token)
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
                        delivery_target,
                        expires_at_ts_ms,
                        sent_at_ts_ms,
                        challenge_status
                    FROM stephen_dcx_user_auth_challenges
                    WHERE otp_hash = %s
                      AND challenge_type = %s
                      AND challenge_purpose = %s
                      AND consumed_at_ts_ms IS NULL
                      AND invalidated_at_ts_ms IS NULL
                    ORDER BY updated_at_ts_ms DESC, id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        phone_link_token_hash,
                        DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
                        DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
                    ),
                )
                challenge_row = cursor.fetchone()

                if challenge_row is None or challenge_row[4] is None:
                    raise RuntimeError("API_DCX_WHATSAPP_PHONE_LINK_TOKEN_INVALID")

                challenge_id = challenge_row[0]
                authenticated_user_id = challenge_row[1]
                target_phone_e164 = challenge_row[2]
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
                    raise RuntimeError("API_DCX_WHATSAPP_PHONE_LINK_TOKEN_EXPIRED")

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
                    raise RuntimeError("API_DCX_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER")

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
                    raise RuntimeError("API_DCX_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_users_contact_methods
                    WHERE user_id = %s
                      AND contact_type = %s
                      AND is_primary = TRUE
                      AND is_active = TRUE
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        authenticated_user_id,
                        "phone",
                    ),
                )
                current_primary_phone_contact_method_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT
                        id,
                        is_primary
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
                should_mark_target_as_primary = (
                    current_primary_phone_contact_method_row is None
                    or (
                        existing_contact_method_row is not None
                        and current_primary_phone_contact_method_row[0] == existing_contact_method_row[0]
                    )
                )

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
                            "primary" if should_mark_target_as_primary else "",
                            should_mark_target_as_primary,
                            False,
                            False,
                            False,
                            True,
                            now_ts_ms,
                            "whatsapp_link",
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
                            contact_value = %s,
                            display_label = %s,
                            is_primary = %s,
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
                            "primary" if should_mark_target_as_primary else "",
                            should_mark_target_as_primary,
                            now_ts_ms,
                            "whatsapp_link",
                            now_ts_ms,
                            now_ts_ms,
                            phone_contact_method_id,
                        ),
                    )

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_user_auth_identities
                    WHERE user_id = %s
                      AND provider_type = %s
                    ORDER BY id ASC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (authenticated_user_id, DCX_WHATSAPP_PHONE_LINK_CHANNEL),
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
                            DCX_WHATSAPP_PHONE_LINK_CHANNEL,
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
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_WHATSAPP_PHONE_LINK_VERIFY_FAILED") from exc

    return {
        "status": "verified",
        "phone_e164": target_phone_e164,
        "whatsapp_identity_id": whatsapp_identity_id,
        "user_id": authenticated_user_id,
        "verified_at_ts_ms": now_ts_ms,
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
