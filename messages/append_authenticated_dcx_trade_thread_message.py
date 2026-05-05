"""
CONTEXT:
This file appends one app-surface message to an existing private trade conversation.

CONTRACT:
- preconditions:
  - authenticated_user_id is a participant in the trade thread.
  - trade_thread_id identifies an open trade thread.
  - message_text contains non-empty human text after trimming.
- postconditions:
  - inserts one stephen_dcx_trade_thread_messages row with source_channel_type app.
  - stores a recipient-language translation when the other participant's preferred language differs.
  - updates the parent thread updated_at timestamp.
  - returns the full refreshed thread detail.
- side_effects:
  - may call Google Gemini for translation before the database write.
  - database insert into stephen_dcx_trade_thread_messages.
  - database update on stephen_dcx_trade_threads.
- idempotent: false for MVP web sends.
- retry_safe: false unless the caller confirms the previous request failed before insertion.
- async: false, blocking database write.
- idempotency_key: not implemented in this MVP web-only mini slice.
- locks: row-level FOR UPDATE lock on stephen_dcx_trade_threads.id.
- contention strategy: wait for PostgreSQL row lock, then append in order.

NARRATIVE:
The MVP needs a simple real back-and-forth chat around trades before we add cross-surface routing.
This capability is intentionally narrow: authenticated app user, existing open thread, plain text.
Use it when the web app composer sends a new private trade-chat message. Do not use it yet for
email or WhatsApp inbound replies, because those surfaces need source-message linking and
idempotency keys. What can go wrong: users can try closed threads, unrelated users can guess ids,
Gemini translation can fail, or duplicate clicks can create duplicate messages. What comes next:
add route keys for email/WhatsApp continuation and per-message delivery fan-out.

TESTS:
- Manual MVP smoke: owner and counterparty each append a message; both see the ordered history after reload.

ERRORS:
- API_DCX_TRADE_THREAD_MESSAGE_EMPTY:
  suggested_action: write a message before sending.
  common_causes: empty or whitespace-only message_text.
  recovery_steps: validate composer text client-side.
  retry_safe: true.
- API_DCX_TRADE_THREAD_NOT_FOUND:
  suggested_action: refresh Trade Chats and choose a current thread.
  common_causes: non-participant access or stale/deleted thread id.
  recovery_steps: reload the thread catalog.
  retry_safe: true.
- API_DCX_TRADE_THREAD_NOT_OPEN:
  suggested_action: use another open conversation or reopen the thread later.
  common_causes: archived or closed conversation.
  recovery_steps: inspect thread_status.
  retry_safe: true.
- API_DCX_TRADE_THREAD_MESSAGE_APPEND_FAILED:
  suggested_action: retry only after confirming the message was not already saved.
  common_causes: database outage or schema drift.
  recovery_steps: inspect logs and refresh the thread detail.
  retry_safe: false.
  what_changed: message insert may or may not have committed.
  rollback_needed: normally false for MVP.
  rollback_operation: delete duplicate message row manually if an operator confirms a duplicate.

CODE:
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from apis.gemini.translate_dcx_gemini_trade_thread_message import (
    translate_dcx_gemini_trade_thread_message,
)
from usage.record_dcx_user_llm_usage_event import record_dcx_user_llm_usage_event
from messages.read_authenticated_dcx_trade_thread_detail import (
    read_authenticated_dcx_trade_thread_detail,
)
from messages.send_dcx_trade_thread_message_notification import (
    send_dcx_trade_thread_message_notification,
)
from storage.db_config import DB_CONFIG


logger = logging.getLogger(__name__)


def append_authenticated_dcx_trade_thread_message(
    authenticated_user_id: int,
    trade_thread_id: int,
    message_text: str,
    language_code: str = "en",
    source_channel_type: str = "app",
    source_contact_message_id: int | None = None,
    notify_other_participant: bool = True,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    normalized_message_text = message_text.strip() if isinstance(message_text, str) else ""
    if not normalized_message_text:
        raise RuntimeError("API_DCX_TRADE_THREAD_MESSAGE_EMPTY")

    normalized_language_code = language_code.strip().lower()[:12] if isinstance(language_code, str) else "en"
    if not normalized_language_code:
        normalized_language_code = "en"
    normalized_source_channel_type = source_channel_type.strip().lower() if isinstance(source_channel_type, str) else "app"
    if normalized_source_channel_type not in {"app", "email", "whatsapp"}:
        normalized_source_channel_type = "app"

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = int(time.time() * 1000)
    inserted_message_id: int | None = None
    recipient_user_id: int | None = None

    try:
        thread_context = _read_trade_thread_append_context(
            connect=connect,
            authenticated_user_id=authenticated_user_id,
            trade_thread_id=trade_thread_id,
        )
        if thread_context is None:
            return None
        if thread_context["thread_status"] != "open":
            raise RuntimeError("API_DCX_TRADE_THREAD_NOT_OPEN")

        target_translation_language_code = (
            thread_context["counterparty_language_code"]
            if thread_context["owner_user_id"] == authenticated_user_id
            else thread_context["owner_language_code"]
        )
        recipient_user_id = (
            thread_context["counterparty_user_id"]
            if thread_context["owner_user_id"] == authenticated_user_id
            else thread_context["owner_user_id"]
        )
        translations_json = _build_trade_thread_message_translations_json(
            message_text=normalized_message_text,
            source_language_code=normalized_language_code,
            target_language_code=target_translation_language_code,
            now_ts_ms=now_ts_ms,
            sender_user_id=authenticated_user_id,
            trade_thread_id=trade_thread_id,
            connect=connect,
        )

        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, thread_status
                    FROM stephen_dcx_trade_threads
                    WHERE id = %s
                      AND (owner_user_id = %s OR counterparty_user_id = %s)
                    FOR UPDATE
                    """,
                    (trade_thread_id, authenticated_user_id, authenticated_user_id),
                )
                locked_thread_row = cursor.fetchone()
                if locked_thread_row is None:
                    return None
                if locked_thread_row[1] != "open":
                    raise RuntimeError("API_DCX_TRADE_THREAD_NOT_OPEN")

                message_summary_text = normalized_message_text[:240]
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_trade_thread_messages (
                        thread_id,
                        source_contact_message_id,
                        sender_user_id,
                        source_channel_type,
                        raw_message_text,
                        canonical_message_text,
                        message_summary_text,
                        language_code,
                        translations_json,
                        message_metadata_json,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        trade_thread_id,
                        source_contact_message_id,
                        authenticated_user_id,
                        normalized_source_channel_type,
                        normalized_message_text,
                        normalized_message_text,
                        message_summary_text,
                        normalized_language_code,
                        Json(translations_json),
                        Json({}),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                inserted_message_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    UPDATE stephen_dcx_trade_threads
                    SET updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (now_ts_ms, trade_thread_id),
                )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_TRADE_THREAD_MESSAGE_APPEND_FAILED") from exc

    if notify_other_participant and recipient_user_id is not None:
        try:
            notification_result = send_dcx_trade_thread_message_notification(
                trade_thread_id=trade_thread_id,
                sender_user_id=authenticated_user_id,
                recipient_user_id=recipient_user_id,
                message_text=normalized_message_text,
                source_trade_thread_message_id=inserted_message_id,
                connect_to_database=connect_to_database,
            )
            logger.info(
                "trade_thread_message_notification_result thread_id=%s sender_user_id=%s recipient_user_id=%s result=%s",
                trade_thread_id,
                authenticated_user_id,
                recipient_user_id,
                notification_result,
            )
        except RuntimeError:
            logger.exception(
                "trade_thread_message_notification_failed thread_id=%s sender_user_id=%s recipient_user_id=%s",
                trade_thread_id,
                authenticated_user_id,
                recipient_user_id,
            )

    return read_authenticated_dcx_trade_thread_detail(
        authenticated_user_id=authenticated_user_id,
        trade_thread_id=trade_thread_id,
        connect_to_database=connect_to_database,
    )


def _read_trade_thread_append_context(
    connect: Callable[..., Any],
    authenticated_user_id: int,
    trade_thread_id: int,
) -> dict | None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    thread.id,
                    thread.thread_status,
                    thread.owner_user_id,
                    thread.counterparty_user_id,
                    COALESCE(owner_language.language_code, 'en') AS owner_language_code,
                    COALESCE(counterparty_language.language_code, 'en') AS counterparty_language_code
                FROM stephen_dcx_trade_threads thread
                INNER JOIN stephen_dcx_users owner_user
                  ON owner_user.id = thread.owner_user_id
                INNER JOIN stephen_dcx_users counterparty_user
                  ON counterparty_user.id = thread.counterparty_user_id
                LEFT JOIN stephen_dcx_languages owner_language
                  ON owner_language.id = owner_user.preferred_language_id
                LEFT JOIN stephen_dcx_languages counterparty_language
                  ON counterparty_language.id = counterparty_user.preferred_language_id
                WHERE thread.id = %s
                  AND (thread.owner_user_id = %s OR thread.counterparty_user_id = %s)
                LIMIT 1
                """,
                (trade_thread_id, authenticated_user_id, authenticated_user_id),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "thread_id": row[0],
        "thread_status": row[1],
        "owner_user_id": row[2],
        "counterparty_user_id": row[3],
        "owner_language_code": row[4],
        "counterparty_language_code": row[5],
    }


def _build_trade_thread_message_translations_json(
    message_text: str,
    source_language_code: str,
    target_language_code: str,
    now_ts_ms: int,
    sender_user_id: int | None = None,
    trade_thread_id: int | None = None,
    connect: Callable[..., Any] | None = None,
) -> dict:
    normalized_source_language_code = source_language_code.strip().lower() if isinstance(source_language_code, str) else "en"
    normalized_target_language_code = target_language_code.strip().lower() if isinstance(target_language_code, str) else "en"
    if normalized_target_language_code == "" or normalized_target_language_code == normalized_source_language_code:
        return {}

    try:
        translation_result = translate_dcx_gemini_trade_thread_message(
            message_text=message_text,
            source_language_code=normalized_source_language_code,
            target_language_code=normalized_target_language_code,
        )
    except RuntimeError:
        return {}
    _record_trade_thread_translation_usage_best_effort(
        sender_user_id=sender_user_id,
        trade_thread_id=trade_thread_id,
        translation_result=translation_result,
        connect=connect,
    )

    return {
        normalized_target_language_code: {
            "text": translation_result["translated_message_text"],
            "translated_from_language_code": normalized_source_language_code,
            "translated_to_language_code": normalized_target_language_code,
            "provider_name": translation_result["provider_name"],
            "model_name": translation_result["model_name"],
            "prompt_version": translation_result["prompt_version"],
            "prompt_fingerprint": translation_result["prompt_fingerprint"],
            "created_at_ts_ms": now_ts_ms,
        }
    }


def _record_trade_thread_translation_usage_best_effort(
    sender_user_id: int | None,
    trade_thread_id: int | None,
    translation_result: dict,
    connect: Callable[..., Any] | None,
) -> None:
    if not isinstance(sender_user_id, int) or sender_user_id <= 0 or connect is None:
        return

    try:
        record_dcx_user_llm_usage_event(
            authenticated_user_id=sender_user_id,
            provider_name=translation_result.get("provider_name", ""),
            model_name=translation_result.get("model_name", ""),
            prompt_version=translation_result.get("prompt_version", ""),
            usage_source_kind="trade_thread_translation",
            usage_source_id=trade_thread_id,
            usage_metadata=(
                translation_result.get("usage_metadata")
                if isinstance(translation_result.get("usage_metadata"), dict)
                else {}
            ),
            connect_to_database=connect,
        )
    except RuntimeError:
        logger.exception(
            "trade_thread_translation_usage_record_failed sender_user_id=%s trade_thread_id=%s",
            sender_user_id,
            trade_thread_id,
        )
