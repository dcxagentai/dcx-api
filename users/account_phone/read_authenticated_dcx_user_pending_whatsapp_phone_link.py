"""
CONTEXT:
This file reads the current pending WhatsApp phone-link state for one authenticated DCX user.
It exists so the app account surface can survive refreshes while a verification-link challenge is
active without promoting an unverified phone number into the user's confirmed profile fields.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG
from users.account_phone.dcx_whatsapp_phone_link_challenge_support import (
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
)


def read_authenticated_dcx_user_pending_whatsapp_phone_link(
    authenticated_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one authenticated DCX user.
        - The configured database is reachable.
      postconditions:
        - Returns the active delivered WhatsApp phone-link challenge summary when one exists.
        - Returns null when no active delivered challenge exists.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The account page needs to know whether the user is mid-verification without overloading
          the confirmed phone fields with pending state.
      WHEN TO USE it:
        - Use it while assembling the authenticated account summary.
      WHEN NOT TO USE it:
        - Do not use it to verify or mutate the challenge.
      WHAT CAN GO WRONG:
        - Database reads can fail.
        - Stale pending rows with no successful delivery should stay hidden from the UI.
      WHAT COMES NEXT:
        - The returned pending state can keep the account page in link-sent mode until the user verifies or requests a new link.

    TESTS:
      - returns_pending_whatsapp_phone_link_when_delivered_challenge_exists
      - returns_null_when_only_undelivered_pending_challenge_exists

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_PENDING_WHATSAPP_PHONE_LINK_READ_FAILED:
          suggested_action: Confirm database health and retry after the backend is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend and database are healthy.
          retry_safe: true

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        return None

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        delivery_target,
                        challenge_status,
                        expires_at_ts_ms,
                        sent_at_ts_ms,
                        next_send_allowed_at_ts_ms,
                        locked_until_ts_ms,
                        resend_count,
                        send_count,
                        last_resent_at_ts_ms
                    FROM stephen_dcx_user_auth_challenges
                    WHERE user_id = %s
                      AND challenge_type = %s
                      AND challenge_purpose = %s
                      AND consumed_at_ts_ms IS NULL
                      AND invalidated_at_ts_ms IS NULL
                      AND sent_at_ts_ms IS NOT NULL
                      AND expires_at_ts_ms >= %s
                    ORDER BY updated_at_ts_ms DESC, id DESC
                    LIMIT 1
                    """,
                    (
                        authenticated_user_id,
                        DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
                        DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
                        now_ts_ms,
                    ),
                )
                challenge_row = cursor.fetchone()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_PENDING_WHATSAPP_PHONE_LINK_READ_FAILED") from exc

    if challenge_row is None:
        return None

    return {
        "phone_e164": challenge_row[0],
        "challenge_status": challenge_row[1],
        "expires_at_ts_ms": challenge_row[2],
        "sent_at_ts_ms": challenge_row[3],
        "next_send_allowed_at_ts_ms": challenge_row[4],
        "locked_until_ts_ms": challenge_row[5],
        "resend_count": challenge_row[6],
        "send_count": challenge_row[7],
        "last_resent_at_ts_ms": challenge_row[8],
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
