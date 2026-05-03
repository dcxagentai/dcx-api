"""
CONTEXT:
This file decides whether one already-stored inbound email/WhatsApp message is a continuation of
an existing private DCX trade conversation.
It exists so provider-origin replies can join the same canonical web-app trade thread instead of
being reclassified as brand-new trade/topic input.

CONTRACT:
- preconditions:
  - contact_message_id identifies one stored inbound stephen_dcx_contact_messages row.
  - the sender has already been resolved to a DCX user/contact method when possible.
- postconditions:
  - Returns None when the message does not contain a valid participant-owned thread reference.
  - Appends exactly one trade-thread message when the message includes a valid #C-style reference.
  - Marks the contact message as ready/completed with workflow metadata showing the routed thread.
- side_effects:
  - may insert into stephen_dcx_trade_thread_messages.
  - may update stephen_dcx_trade_threads.updated_at_ts_ms.
  - may update stephen_dcx_contact_messages status/metadata.
  - may send one notification to the other thread participant.
- idempotent: true for the same source_contact_message_id because existing routed thread messages are reused.
- retry_safe: true.
- async: false, blocking database/provider work.
- idempotency_key: inbound_trade_thread_reply:{contact_message_id}
- locks: append capability locks stephen_dcx_trade_threads.id FOR UPDATE.
- contention strategy: duplicate provider webhooks converge because source_contact_message_id is checked before append.

NARRATIVE:
WHY this exists:
  The MVP now has private trade conversations on the web app, but traders naturally reply from
  email and WhatsApp. Provider messages should become chat turns when the trader supplies the
  explicit conversation reference, for example #C12.
WHEN TO USE it:
  Use it after the provider message has been persisted and attachments stored, before normal
  classification/routing.
WHEN NOT TO USE it:
  Do not use it for app-originated sends. Do not route messages that merely mention a code unless
  the sender is one of the two participants.
WHAT CAN GO WRONG:
  Traders can omit the reference, use a stale/closed thread, or send from an unlinked address/phone.
WHAT COMES NEXT:
  Provider reply-id correlation can complement #C references later; the explicit reference remains
  a useful fallback and support/debug handle.

TESTS:
- Manual MVP smoke: email reply "#C1 yes, interested" appears in Trade Chats and does not create a new trade.
- Manual MVP smoke: WhatsApp reply "#C1 price?" appears in Trade Chats and notifies the other participant.
- Manual MVP smoke: non-participant message with "#C1" falls through to normal classification.

ERRORS:
- API_DCX_INBOUND_TRADE_THREAD_ROUTE_FAILED:
  suggested_action: allow the message to fall back to normal message processing after inspecting logs.
  common_causes: schema drift, database outage, append capability failure.
  recovery_steps: confirm thread id/reference, contact resolution, and database health.
  retry_safe: true.
  what_changed: contact message may already be stored.
  rollback_needed: false unless a duplicate thread message was manually created.
  rollback_operation: delete duplicate stephen_dcx_trade_thread_messages row after operator review.

CODE:
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from messages.append_authenticated_dcx_trade_thread_message import (
    append_authenticated_dcx_trade_thread_message,
)
from messages.send_dcx_trade_thread_message_notification import (
    upsert_dcx_trade_thread_participant_route,
)
from storage.db_config import DB_CONFIG

TRADE_THREAD_REFERENCE_PATTERN = re.compile(r"(?:^|[\s#])C(?P<thread_id>[0-9]{1,12})(?=\b)", re.IGNORECASE)
EMAIL_REPLY_QUOTE_BOUNDARY_PATTERNS = [
    re.compile(r"^replying to .+", re.IGNORECASE),
    re.compile(r"^on .+ wrote:$", re.IGNORECASE),
    re.compile(r"^(from|to|cc|bcc|date|sent|subject):\s*.+", re.IGNORECASE),
]


def route_dcx_inbound_contact_message_to_trade_thread_if_applicable(
    contact_message_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = int(time.time() * 1000)

    try:
        message_context = _read_inbound_contact_message_trade_thread_route_context(
            connect=connect,
            contact_message_id=contact_message_id,
        )
        if message_context is None:
            return None
        if message_context["user_id"] is None:
            return None

        thread_reference_code = _extract_trade_thread_reference_code(
            f"{message_context['message_subject']}\n{message_context['raw_text_content']}"
        )
        if thread_reference_code is None:
            return None

        thread_context = _read_referenced_trade_thread_for_participant(
            connect=connect,
            thread_reference_code=thread_reference_code,
            participant_user_id=message_context["user_id"],
        )
        if thread_context is None:
            return None

        existing_thread_message_id = _read_existing_thread_message_id_for_contact_message(
            connect=connect,
            contact_message_id=contact_message_id,
        )
        if existing_thread_message_id is not None:
            _mark_contact_message_as_trade_thread_routed(
                connect=connect,
                contact_message_id=contact_message_id,
                thread_id=thread_context["thread_id"],
                thread_reference_code=thread_context["thread_reference_code"],
                now_ts_ms=now_ts_ms,
            )
            return {
                "routed": True,
                "trade_thread_id": thread_context["thread_id"],
                "thread_reference_code": thread_context["thread_reference_code"],
                "trade_thread_message_id": existing_thread_message_id,
                "processing_status": "ready",
                "derivation_status": "completed",
            }

        routed_message_text = _build_routed_trade_thread_message_text(
            message_subject=message_context["message_subject"],
            message_text=message_context["raw_text_content"],
            thread_reference_code=thread_reference_code,
            include_subject=message_context["channel_type"] == "email",
        )
        if routed_message_text == "":
            return None

        upsert_dcx_trade_thread_participant_route(
            trade_thread_id=thread_context["thread_id"],
            user_id=message_context["user_id"],
            current_route_channel=message_context["channel_type"],
            current_route_contact_method_id=message_context["contact_method_id"],
            route_source="latest_reply",
            connect_to_database=connect,
        )

        append_authenticated_dcx_trade_thread_message(
            authenticated_user_id=message_context["user_id"],
            trade_thread_id=thread_context["thread_id"],
            message_text=routed_message_text,
            language_code=message_context["preferred_language_code"],
            source_channel_type=message_context["channel_type"],
            source_contact_message_id=contact_message_id,
            notify_other_participant=True,
            connect_to_database=connect,
        )
        routed_message_id = _read_existing_thread_message_id_for_contact_message(
            connect=connect,
            contact_message_id=contact_message_id,
        )
        _mark_contact_message_as_trade_thread_routed(
            connect=connect,
            contact_message_id=contact_message_id,
            thread_id=thread_context["thread_id"],
            thread_reference_code=thread_context["thread_reference_code"],
            now_ts_ms=now_ts_ms,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_INBOUND_TRADE_THREAD_ROUTE_FAILED") from exc

    return {
        "routed": True,
        "trade_thread_id": thread_context["thread_id"],
        "thread_reference_code": thread_context["thread_reference_code"],
        "trade_thread_message_id": routed_message_id,
        "processing_status": "ready",
        "derivation_status": "completed",
    }


def _read_inbound_contact_message_trade_thread_route_context(
    connect: Callable[..., Any],
    contact_message_id: int,
) -> dict | None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    message.id,
                    message.user_id,
                    message.contact_method_id,
                    message.channel_type,
                    message.message_subject,
                    message.raw_text_content,
                    COALESCE(language.language_code, 'en') AS preferred_language_code
                FROM stephen_dcx_contact_messages message
                LEFT JOIN stephen_dcx_users user_row
                  ON user_row.id = message.user_id
                LEFT JOIN stephen_dcx_languages language
                  ON language.id = user_row.preferred_language_id
                WHERE message.id = %s
                  AND message.message_direction = 'inbound'
                  AND message.channel_type IN ('email', 'whatsapp')
                LIMIT 1
                """,
                (contact_message_id,),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "message_id": row[0],
        "user_id": row[1],
        "contact_method_id": row[2],
        "channel_type": row[3],
        "message_subject": row[4] or "",
        "raw_text_content": row[5] or "",
        "preferred_language_code": row[6] or "en",
    }


def _extract_trade_thread_reference_code(text: str) -> str | None:
    normalized_text = text if isinstance(text, str) else ""
    match = TRADE_THREAD_REFERENCE_PATTERN.search(normalized_text)
    if match is None:
        return None
    return f"C{match.group('thread_id')}"


def _read_referenced_trade_thread_for_participant(
    connect: Callable[..., Any],
    thread_reference_code: str,
    participant_user_id: int,
) -> dict | None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, thread_reference_code
                FROM stephen_dcx_trade_threads
                WHERE lower(thread_reference_code) = lower(%s)
                  AND thread_status = 'open'
                  AND (owner_user_id = %s OR counterparty_user_id = %s)
                LIMIT 1
                """,
                (thread_reference_code, participant_user_id, participant_user_id),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "thread_id": row[0],
        "thread_reference_code": row[1],
    }


def _read_existing_thread_message_id_for_contact_message(
    connect: Callable[..., Any],
    contact_message_id: int,
) -> int | None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM stephen_dcx_trade_thread_messages
                WHERE source_contact_message_id = %s
                ORDER BY id ASC
                LIMIT 1
                """,
                (contact_message_id,),
            )
            row = cursor.fetchone()

    return row[0] if row is not None else None


def _strip_trade_thread_reference_from_message_text(message_text: str, thread_reference_code: str) -> str:
    normalized_message_text = message_text.strip() if isinstance(message_text, str) else ""
    if normalized_message_text == "":
        return ""

    stripped_lines = []
    for raw_line in normalized_message_text.splitlines():
        line = raw_line.strip()
        if line == "":
            continue
        if line.startswith(">") or _read_line_is_email_reply_quote_boundary(line):
            break
        if "open in dcx:" in line.lower() or "reply with #" in line.lower():
            continue
        stripped_lines.append(line)

    stripped_text = "\n".join(stripped_lines)
    stripped_text = re.sub(rf"#?{re.escape(thread_reference_code)}\b", "", stripped_text, flags=re.IGNORECASE)
    return stripped_text.strip()


def _build_routed_trade_thread_message_text(
    message_subject: str,
    message_text: str,
    thread_reference_code: str,
    include_subject: bool,
) -> str:
    body_text = _strip_trade_thread_reference_from_message_text(
        message_text=message_text,
        thread_reference_code=thread_reference_code,
    )
    if not include_subject:
        return body_text

    subject_text = _strip_trade_thread_reference_from_subject(
        message_subject=message_subject,
        thread_reference_code=thread_reference_code,
    )
    if subject_text == "":
        return body_text
    if body_text == "":
        return subject_text
    if subject_text.lower() == body_text.lower():
        return body_text
    return f"{subject_text}\n\n{body_text}"


def _strip_trade_thread_reference_from_subject(message_subject: str, thread_reference_code: str) -> str:
    normalized_subject = message_subject.strip() if isinstance(message_subject, str) else ""
    if normalized_subject == "":
        return ""

    while True:
        stripped_subject = re.sub(r"^(re|fw|fwd):\s*", "", normalized_subject, flags=re.IGNORECASE)
        if stripped_subject == normalized_subject:
            break
        normalized_subject = stripped_subject.strip()

    normalized_subject = re.sub(
        rf"#?{re.escape(thread_reference_code)}\b",
        "",
        normalized_subject,
        flags=re.IGNORECASE,
    )
    normalized_subject = re.sub(r"\s+", " ", normalized_subject).strip(" #-:|")
    if normalized_subject.lower() in {"dcx trade chat", "trade chat", "new dcx trade chat message in"}:
        return ""
    return normalized_subject


def _read_line_is_email_reply_quote_boundary(line: str) -> bool:
    normalized_line = line.strip() if isinstance(line, str) else ""
    if normalized_line == "":
        return False
    return any(pattern.match(normalized_line) is not None for pattern in EMAIL_REPLY_QUOTE_BOUNDARY_PATTERNS)


def _mark_contact_message_as_trade_thread_routed(
    connect: Callable[..., Any],
    contact_message_id: int,
    thread_id: int,
    thread_reference_code: str,
    now_ts_ms: int,
) -> None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE stephen_dcx_contact_messages
                SET
                    processing_status = 'ready',
                    derivation_status = 'completed',
                    analysis_status = 'completed',
                    analysis_summary_text = %s,
                    workflow_classification_status = 'completed',
                    primary_workflow_kind = NULL,
                    contains_trade_items = FALSE,
                    contains_market_topic_items = FALSE,
                    contains_other_items = FALSE,
                    workflow_reason_summary = %s,
                    workflow_metadata_json = workflow_metadata_json || %s::jsonb,
                    analysis_completed_at_ts_ms = %s,
                    updated_at_ts_ms = %s
                WHERE id = %s
                """,
                (
                    f"Routed to private trade conversation {thread_reference_code}.",
                    f"Routed to private trade conversation {thread_reference_code}.",
                    Json(
                        {
                            "trade_thread_routing": {
                                "routed": True,
                                "trade_thread_id": thread_id,
                                "thread_reference_code": thread_reference_code,
                            }
                        }
                    ),
                    now_ts_ms,
                    now_ts_ms,
                    contact_message_id,
                ),
            )
