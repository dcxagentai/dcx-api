"""
CONTEXT:
This file reads one private trader-to-trader trade conversation for a participant.

CONTRACT:
- preconditions:
  - authenticated_user_id is a positive integer.
  - trade_thread_id is a positive integer.
- postconditions:
  - returns the trade thread and ordered messages only when the authenticated user is a participant.
  - returns None when the thread does not exist or the user is not allowed to see it.
- side_effects: []
- idempotent: true
- retry_safe: true
- async: false, blocking database read.

NARRATIVE:
This is the privacy boundary for private trade conversations. The thread is visible to the trade
owner and the interested counterparty only. Use this for the web app Trade Chat detail panel and,
later, for email/WhatsApp thread continuation routing. Do not use this for global market deals,
global forum posts, or admin legal review. What can go wrong: an unrelated user may ask for a
thread id, in which case the correct response is indistinguishable from not found.

TESTS:
- Manual MVP smoke: user A publishes a trade, user B starts a discussion, then both users can open
  the thread while user C cannot.

ERRORS:
- API_DCX_TRADE_THREAD_DETAIL_READ_FAILED:
  suggested_action: retry after confirming the database is reachable.
  common_causes: database outage or schema drift.
  recovery_steps: inspect route logs and thread/message tables.
  retry_safe: true.

CODE:
"""

from __future__ import annotations

import json
from typing import Any, Callable

import psycopg2

from messages.read_authenticated_dcx_source_message_first_image_attachment import (
    read_authenticated_dcx_source_message_first_image_attachment,
)
from storage.db_config import DB_CONFIG


def read_authenticated_dcx_trade_thread_detail(
    authenticated_user_id: int,
    trade_thread_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        return None
    if not isinstance(trade_thread_id, int) or trade_thread_id <= 0:
        return None

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
                authenticated_user_language_code = (
                    authenticated_user_language_row[0] if authenticated_user_language_row is not None else "en"
                )

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
                        trade.source_message_id_initial,
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
                        END AS counterparty_public_identity_label
                    FROM stephen_dcx_trade_threads thread
                    INNER JOIN stephen_dcx_trades trade
                      ON trade.id = thread.trade_id
                    INNER JOIN stephen_dcx_trade_versions trade_version
                      ON trade_version.id = trade.current_version_id
                    INNER JOIN stephen_dcx_users owner_user
                      ON owner_user.id = thread.owner_user_id
                    INNER JOIN stephen_dcx_users counterparty_user
                      ON counterparty_user.id = thread.counterparty_user_id
                    WHERE thread.id = %s
                      AND (thread.owner_user_id = %s OR thread.counterparty_user_id = %s)
                    LIMIT 1
                    """,
                    (trade_thread_id, authenticated_user_id, authenticated_user_id),
                )
                thread_row = cursor.fetchone()
                if thread_row is None:
                    return None
                source_first_image_attachment = read_authenticated_dcx_source_message_first_image_attachment(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    source_message_id=thread_row[19],
                )

                cursor.execute(
                    """
                    SELECT
                        message.id,
                        message.thread_id,
                        message.sender_user_id,
                        CASE
                          WHEN sender_user.public_identity_mode = 'anonymous' THEN 'Trader #' || sender_user.id::text
                          WHEN sender_user.public_identity_mode = 'handle' AND NULLIF(sender_user.public_handle, '') IS NOT NULL THEN '@' || sender_user.public_handle
                          WHEN NULLIF(sender_user.public_display_name, '') IS NOT NULL THEN sender_user.public_display_name
                          WHEN NULLIF(sender_user.public_handle, '') IS NOT NULL THEN '@' || sender_user.public_handle
                          ELSE 'Trader #' || sender_user.id::text
                        END AS sender_public_identity_label,
                        message.source_channel_type,
                        message.raw_message_text,
                        message.canonical_message_text,
                        message.message_summary_text,
                        message.language_code,
                        message.translations_json,
                        message.created_at_ts_ms,
                        message.updated_at_ts_ms
                    FROM stephen_dcx_trade_thread_messages message
                    INNER JOIN stephen_dcx_users sender_user
                      ON sender_user.id = message.sender_user_id
                    WHERE message.thread_id = %s
                    ORDER BY message.created_at_ts_ms ASC, message.id ASC
                    """,
                    (trade_thread_id,),
                )
                message_rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError("API_DCX_TRADE_THREAD_DETAIL_READ_FAILED") from exc

    is_owner = thread_row[5] == authenticated_user_id
    return {
        "trade_thread_id": thread_row[0],
        "thread_reference_code": thread_row[1],
        "thread_status": thread_row[2],
        "trade_id": thread_row[3],
        "trade_publication_id": thread_row[4],
        "owner_user_id": thread_row[5],
        "counterparty_user_id": thread_row[6],
        "created_at_ts_ms": thread_row[7],
        "updated_at_ts_ms": thread_row[8],
        "trade_summary_text": thread_row[9],
        "normalized_trade_side": thread_row[10],
        "normalized_material_name": thread_row[11],
        "normalized_quantity_value": float(thread_row[12]) if thread_row[12] is not None else None,
        "normalized_quantity_unit": thread_row[13],
        "normalized_price_value": float(thread_row[14]) if thread_row[14] is not None else None,
        "normalized_price_unit_basis": thread_row[15],
        "normalized_currency_code": thread_row[16],
        "normalized_origin_location": thread_row[17],
        "normalized_destination_location": thread_row[18],
        "source_message_id": thread_row[19],
        "source_first_image_attachment": source_first_image_attachment,
        "owner_public_identity_label": thread_row[20],
        "counterparty_public_identity_label": thread_row[21],
        "other_participant_public_identity_label": thread_row[21] if is_owner else thread_row[20],
        "is_authenticated_user_owner": is_owner,
        "messages": [
            _format_trade_thread_message_row(
                row=row,
                authenticated_user_id=authenticated_user_id,
                authenticated_user_language_code=authenticated_user_language_code,
            )
            for row in message_rows
        ],
    }


def _format_trade_thread_message_row(
    row: tuple,
    authenticated_user_id: int,
    authenticated_user_language_code: str,
) -> dict:
    translations_json = _coerce_translations_json(row[9])
    display_message_text = row[6]
    displayed_translation_language_code = None
    translated_from_language_code = None
    normalized_language_code = (
        authenticated_user_language_code.strip().lower()
        if isinstance(authenticated_user_language_code, str)
        else "en"
    ) or "en"

    if row[2] != authenticated_user_id:
        translation_entry = translations_json.get(normalized_language_code)
        if isinstance(translation_entry, dict):
            translated_text = str(translation_entry.get("text") or "").strip()
            if translated_text:
                display_message_text = translated_text
                displayed_translation_language_code = normalized_language_code
                translated_from_language_code = translation_entry.get("translated_from_language_code")

    return {
        "trade_thread_message_id": row[0],
        "thread_id": row[1],
        "sender_user_id": row[2],
        "sender_public_identity_label": row[3],
        "is_sent_by_authenticated_user": row[2] == authenticated_user_id,
        "source_channel_type": row[4],
        "raw_message_text": row[5],
        "canonical_message_text": row[6],
        "display_message_text": display_message_text,
        "message_summary_text": row[7],
        "language_code": row[8],
        "displayed_translation_language_code": displayed_translation_language_code,
        "translated_from_language_code": translated_from_language_code,
        "translations_json": translations_json,
        "created_at_ts_ms": row[10],
        "updated_at_ts_ms": row[11],
    }


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
