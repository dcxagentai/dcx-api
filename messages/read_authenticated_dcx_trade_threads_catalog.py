"""
CONTEXT:
This file reads the private trade conversation catalog for one authenticated DCX user.

CONTRACT:
- preconditions:
  - authenticated_user_id is a positive integer for a logged-in DCX user.
- postconditions:
  - returns only trade threads where the user is the trade owner or the counterparty.
  - includes enough trade summary and latest-message context for the app list view.
- side_effects: []
- idempotent: true
- retry_safe: true
- async: false, blocking database read.

NARRATIVE:
Trader-to-trader conversations are not the same object as trades. A single published trade may
lead to multiple private counterparty conversations. This reader gives the app a private inbox of
those conversation spines without exposing conversations to anyone outside the two participants.
Use it for the authenticated web app Trade Chats list. Do not use it for public market listings or
cross-surface webhook routing. What can go wrong: the user id may be invalid, the database may be
unavailable, or a thread may point at a trade missing a current version. What comes next: email and
WhatsApp routing can later reuse the same table as the canonical private conversation spine.

TESTS:
- Manual MVP smoke: start a discussion from Market Deals as a second user, then verify both users
  see the thread in their Trade Chats catalog and unrelated users do not.

ERRORS:
- API_DCX_TRADE_THREADS_USER_NOT_FOUND:
  suggested_action: refresh the session and sign in again.
  common_causes: invalid authenticated user id.
  recovery_steps: require authentication before calling this capability.
  retry_safe: true.
- API_DCX_TRADE_THREADS_CATALOG_READ_FAILED:
  suggested_action: retry after confirming the database is reachable.
  common_causes: database outage or schema drift.
  recovery_steps: inspect backend logs and schema for thread/trade version tables.
  retry_safe: true.

CODE:
"""

from __future__ import annotations

import json
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_authenticated_dcx_trade_threads_catalog(
    authenticated_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_DCX_TRADE_THREADS_USER_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(language.language_code, 'en')
                    FROM stephen_dcx_users user_row
                    LEFT JOIN stephen_dcx_languages language
                      ON language.id = user_row.preferred_language_id
                    WHERE user_row.id = %s
                    LIMIT 1
                    """,
                    (authenticated_user_id,),
                )
                authenticated_user_language_row = cursor.fetchone()
                if authenticated_user_language_row is None:
                    raise RuntimeError("API_DCX_TRADE_THREADS_USER_NOT_FOUND")
                authenticated_user_language_code = authenticated_user_language_row[0] or "en"

                cursor.execute(
                    """
                    SELECT
                        thread.id,
                        thread.thread_reference_code,
                        thread.thread_status,
                        thread.trade_id,
                        thread.trade_publication_id,
                        thread.owner_user_id,
                        thread.counterparty_user_id,
                        thread.created_at_ts_ms,
                        thread.updated_at_ts_ms,
                        trade_version.trade_summary_text,
                        trade_version.normalized_trade_side,
                        trade_version.normalized_material_name,
                        trade_version.normalized_quantity_value,
                        trade_version.normalized_quantity_unit,
                        trade_version.normalized_price_value,
                        trade_version.normalized_price_unit_basis,
                        trade_version.normalized_currency_code,
                        trade_version.normalized_origin_location,
                        trade_version.normalized_destination_location,
                        CASE
                          WHEN owner_user.public_identity_mode = 'anonymous' THEN 'Trader #' || owner_user.id::text
                          WHEN owner_user.public_identity_mode = 'handle' AND NULLIF(owner_user.public_handle, '') IS NOT NULL THEN '@' || owner_user.public_handle
                          WHEN NULLIF(owner_user.public_display_name, '') IS NOT NULL THEN owner_user.public_display_name
                          WHEN NULLIF(owner_user.public_handle, '') IS NOT NULL THEN '@' || owner_user.public_handle
                          ELSE 'Trader #' || owner_user.id::text
                        END AS owner_public_identity_label,
                        CASE
                          WHEN counterparty_user.public_identity_mode = 'anonymous' THEN 'Trader #' || counterparty_user.id::text
                          WHEN counterparty_user.public_identity_mode = 'handle' AND NULLIF(counterparty_user.public_handle, '') IS NOT NULL THEN '@' || counterparty_user.public_handle
                          WHEN NULLIF(counterparty_user.public_display_name, '') IS NOT NULL THEN counterparty_user.public_display_name
                          WHEN NULLIF(counterparty_user.public_handle, '') IS NOT NULL THEN '@' || counterparty_user.public_handle
                          ELSE 'Trader #' || counterparty_user.id::text
                        END AS counterparty_public_identity_label,
                        COALESCE(message_stats.message_count, 0) AS message_count,
                        latest_message.canonical_message_text AS latest_message_text,
                        latest_message.language_code AS latest_message_language_code,
                        latest_message.translations_json AS latest_message_translations_json,
                        latest_message.sender_user_id AS latest_message_sender_user_id,
                        latest_message.created_at_ts_ms AS latest_message_created_at_ts_ms
                    FROM stephen_dcx_trade_threads thread
                    INNER JOIN stephen_dcx_trades trade
                      ON trade.id = thread.trade_id
                    INNER JOIN stephen_dcx_trade_versions trade_version
                      ON trade_version.id = trade.current_version_id
                    INNER JOIN stephen_dcx_users owner_user
                      ON owner_user.id = thread.owner_user_id
                    INNER JOIN stephen_dcx_users counterparty_user
                      ON counterparty_user.id = thread.counterparty_user_id
                    LEFT JOIN LATERAL (
                        SELECT COUNT(*)::integer AS message_count
                        FROM stephen_dcx_trade_thread_messages message_count_row
                        WHERE message_count_row.thread_id = thread.id
                    ) message_stats ON true
                    LEFT JOIN LATERAL (
                        SELECT
                            message_row.canonical_message_text,
                            message_row.language_code,
                            message_row.translations_json,
                            message_row.sender_user_id,
                            message_row.created_at_ts_ms
                        FROM stephen_dcx_trade_thread_messages message_row
                        WHERE message_row.thread_id = thread.id
                        ORDER BY message_row.created_at_ts_ms DESC, message_row.id DESC
                        LIMIT 1
                    ) latest_message ON true
                    WHERE thread.owner_user_id = %s
                       OR thread.counterparty_user_id = %s
                    ORDER BY thread.updated_at_ts_ms DESC, thread.id DESC
                    """,
                    (authenticated_user_id, authenticated_user_id),
                )
                thread_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_TRADE_THREADS_CATALOG_READ_FAILED") from exc

    trade_threads = []
    for row in thread_rows:
        is_owner = row[5] == authenticated_user_id
        trade_threads.append(
            {
                "trade_thread_id": row[0],
                "thread_reference_code": row[1],
                "thread_status": row[2],
                "trade_id": row[3],
                "trade_publication_id": row[4],
                "owner_user_id": row[5],
                "counterparty_user_id": row[6],
                "created_at_ts_ms": row[7],
                "updated_at_ts_ms": row[8],
                "trade_summary_text": row[9],
                "normalized_trade_side": row[10],
                "normalized_material_name": row[11],
                "normalized_quantity_value": float(row[12]) if row[12] is not None else None,
                "normalized_quantity_unit": row[13],
                "normalized_price_value": float(row[14]) if row[14] is not None else None,
                "normalized_price_unit_basis": row[15],
                "normalized_currency_code": row[16],
                "normalized_origin_location": row[17],
                "normalized_destination_location": row[18],
                "owner_public_identity_label": row[19],
                "counterparty_public_identity_label": row[20],
                "other_participant_public_identity_label": row[20] if is_owner else row[19],
                "is_authenticated_user_owner": is_owner,
                "message_count": row[21],
                "latest_message_text": _read_display_latest_message_text(
                    canonical_message_text=row[22],
                    translations_json=row[24],
                    sender_user_id=row[25],
                    authenticated_user_id=authenticated_user_id,
                    authenticated_user_language_code=authenticated_user_language_code,
                ),
                "latest_message_created_at_ts_ms": row[26],
            }
        )

    return {
        "trade_threads": trade_threads,
        "total_trade_thread_count": len(trade_threads),
    }


def _read_display_latest_message_text(
    canonical_message_text: str | None,
    translations_json: Any,
    sender_user_id: int | None,
    authenticated_user_id: int,
    authenticated_user_language_code: str,
) -> str | None:
    if canonical_message_text is None:
        return None
    if sender_user_id == authenticated_user_id:
        return canonical_message_text

    normalized_language_code = (
        authenticated_user_language_code.strip().lower()
        if isinstance(authenticated_user_language_code, str)
        else "en"
    ) or "en"
    translations = _coerce_translations_json(translations_json)
    translation_entry = translations.get(normalized_language_code)
    if isinstance(translation_entry, dict):
        translated_text = str(translation_entry.get("text") or "").strip()
        if translated_text:
            return translated_text
    return canonical_message_text


def _coerce_translations_json(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed_value if isinstance(parsed_value, dict) else {}
    return {}
