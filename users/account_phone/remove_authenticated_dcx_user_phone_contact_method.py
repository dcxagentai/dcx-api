"""
CONTEXT:
This file deactivates one unused phone contact method for an authenticated DCX user.
It exists so users can clean up mistaken/unverified phone entries without breaking historical
message, trade, or provider attribution.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG
from users.account_phone.dcx_whatsapp_phone_link_challenge_support import (
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
    DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
)


def remove_authenticated_dcx_user_phone_contact_method(
    authenticated_user_id: int,
    phone_contact_method_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND")
    if not isinstance(phone_contact_method_id, int) or phone_contact_method_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        normalized_value,
                        is_primary
                    FROM stephen_dcx_users_contact_methods
                    WHERE id = %s
                      AND user_id = %s
                      AND contact_type = %s
                      AND is_active = TRUE
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        phone_contact_method_id,
                        authenticated_user_id,
                        "phone",
                    ),
                )
                contact_method_row = cursor.fetchone()
                if contact_method_row is None:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_FOUND")

                normalized_phone_e164 = contact_method_row[1]
                if contact_method_row[2] is True:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_REMOVE_BLOCKED_PRIMARY")

                blocking_reference = _read_first_blocking_reference(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    phone_contact_method_id=phone_contact_method_id,
                )
                if blocking_reference is not None:
                    raise RuntimeError(
                        "API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_REMOVE_BLOCKED:"
                        + blocking_reference
                    )

                cursor.execute(
                    """
                    UPDATE stephen_dcx_user_auth_challenges
                    SET
                        challenge_status = %s,
                        invalidated_at_ts_ms = %s,
                        updated_at_ts_ms = %s
                    WHERE user_id = %s
                      AND challenge_type = %s
                      AND challenge_purpose = %s
                      AND delivery_target = %s
                      AND consumed_at_ts_ms IS NULL
                      AND invalidated_at_ts_ms IS NULL
                    """,
                    (
                        "invalidated",
                        now_ts_ms,
                        now_ts_ms,
                        authenticated_user_id,
                        DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE,
                        DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE,
                        normalized_phone_e164,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_contact_method_channel_confirmations
                    SET
                        confirmation_status = %s,
                        updated_at_ts_ms = %s
                    WHERE user_id = %s
                      AND contact_method_id = %s
                      AND confirmation_status IN ('pending', 'sent')
                    """,
                    (
                        "invalidated",
                        now_ts_ms,
                        authenticated_user_id,
                        phone_contact_method_id,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_users_contact_methods
                    SET
                        is_active = FALSE,
                        is_primary = FALSE,
                        is_login_enabled = FALSE,
                        is_recovery_enabled = FALSE,
                        is_notification_enabled = FALSE,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                      AND user_id = %s
                    RETURNING id
                    """,
                    (
                        now_ts_ms,
                        phone_contact_method_id,
                        authenticated_user_id,
                    ),
                )
                updated_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_REMOVE_FAILED") from exc

    if updated_row is None:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_FOUND")

    return {
        "status": "removed",
        "phone_contact_method_id": phone_contact_method_id,
    }


def _read_first_blocking_reference(
    cursor: Any,
    authenticated_user_id: int,
    phone_contact_method_id: int,
) -> str | None:
    checks = [
        (
            "auth_identity",
            """
            SELECT 1
            FROM stephen_dcx_user_auth_identities
            WHERE user_id = %s
              AND contact_method_id = %s
            LIMIT 1
            """,
        ),
        (
            "contact_message",
            """
            SELECT 1
            FROM stephen_dcx_contact_messages
            WHERE user_id = %s
              AND contact_method_id = %s
            LIMIT 1
            """,
        ),
        (
            "provider_event",
            """
            SELECT 1
            FROM stephen_dcx_contact_message_provider_events
            WHERE user_id = %s
              AND contact_method_id = %s
            LIMIT 1
            """,
        ),
        (
            "trade",
            """
            SELECT 1
            FROM stephen_dcx_trades
            WHERE initiating_user_id = %s
              AND initiating_contact_method_id = %s
            LIMIT 1
            """,
        ),
        (
            "market_topic",
            """
            SELECT 1
            FROM stephen_dcx_market_topics
            WHERE initiating_user_id = %s
              AND initiating_contact_method_id = %s
            LIMIT 1
            """,
        ),
        (
            "trade_thread_route",
            """
            SELECT 1
            FROM stephen_dcx_trade_thread_participant_routes
            WHERE user_id = %s
              AND current_route_contact_method_id = %s
            LIMIT 1
            """,
        ),
        (
            "confirmed_channel_origin",
            """
            SELECT 1
            FROM stephen_dcx_contact_method_channel_confirmations
            WHERE user_id = %s
              AND contact_method_id = %s
              AND confirmation_status = 'confirmed'
            LIMIT 1
            """,
        ),
    ]

    for reference_name, sql in checks:
        cursor.execute(sql, (authenticated_user_id, phone_contact_method_id))
        if cursor.fetchone() is not None:
            return reference_name

    return None


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
