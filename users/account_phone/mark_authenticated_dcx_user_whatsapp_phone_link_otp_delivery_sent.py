"""
CONTEXT:
This file marks one prepared WhatsApp phone-link OTP challenge as successfully delivered.
It exists so the account-phone flow can keep cooldown and pending-summary behavior tied to
real provider delivery success rather than merely to challenge preparation.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG
from users.account_phone.dcx_whatsapp_phone_link_challenge_support import (
    DCX_WHATSAPP_PHONE_LINK_SEND_COOLDOWN_MS,
)
from users.account_phone.dcx_channel_origin_confirmation_support import (
    mark_contact_method_channel_origin_confirmation_sent,
)


def mark_authenticated_dcx_user_whatsapp_phone_link_otp_delivery_sent(
    authenticated_user_id: int,
    challenge_id: int,
    provider_message_id: str | None = None,
    template_name: str | None = None,
    template_language_code: str | None = None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> None:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies the owner of the pending phone-link challenge.
        - challenge_id identifies one prepared pending challenge row.
      postconditions:
        - Marks the challenge as delivered now.
        - Starts the resend cooldown window.
      side_effects:
        - updates stephen_dcx_user_auth_challenges
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Phone-link resend cooldown should start only after the provider actually accepted the outbound WhatsApp OTP.
      WHEN TO USE it:
        - Use it immediately after the provider adapter accepts the OTP send.
      WHEN NOT TO USE it:
        - Do not use it when the provider send failed.
      WHAT CAN GO WRONG:
        - The challenge can be missing or belong to another user.
      WHAT COMES NEXT:
        - The account summary can now surface the pending delivered challenge to the app UI.

    TESTS:
      - marks_pending_challenge_as_delivered_and_sets_cooldown

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_CHALLENGE_NOT_FOUND:
          suggested_action: Request a new WhatsApp code and retry.
          common_causes:
            - stale challenge id
            - challenge already consumed or invalidated
          recovery_steps:
            - Start the phone-link send again from the account page.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_DELIVERY_MARK_FAILED:
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
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE stephen_dcx_user_auth_challenges
                    SET
                        sent_at_ts_ms = %s,
                        next_send_allowed_at_ts_ms = %s,
                        last_resent_at_ts_ms = CASE
                            WHEN send_count > 1 THEN %s
                            ELSE last_resent_at_ts_ms
                        END,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                      AND user_id = %s
                      AND consumed_at_ts_ms IS NULL
                      AND invalidated_at_ts_ms IS NULL
                    RETURNING id
                    """,
                    (
                        now_ts_ms,
                        now_ts_ms + DCX_WHATSAPP_PHONE_LINK_SEND_COOLDOWN_MS,
                        now_ts_ms,
                        now_ts_ms,
                        challenge_id,
                        authenticated_user_id,
                    ),
                )
                updated_row = cursor.fetchone()
                if updated_row is not None:
                    mark_contact_method_channel_origin_confirmation_sent(
                        cursor=cursor,
                        user_id=authenticated_user_id,
                        auth_challenge_id=challenge_id,
                        provider_message_id=provider_message_id,
                        template_name=template_name,
                        template_language_code=template_language_code,
                        sent_at_ts_ms=now_ts_ms,
                    )
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_DELIVERY_MARK_FAILED") from exc

    if updated_row is None:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_CHALLENGE_NOT_FOUND")


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
