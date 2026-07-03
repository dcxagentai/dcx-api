"""
CONTEXT:
This file decides whether one already-stored inbound email/WhatsApp message is a continuation of
an existing private DCX market-topic AI conversation.
It exists so traders can use `#AI` references from email or WhatsApp to keep chatting with DCX AI
about a previously opened market topic.

CONTRACT:
- preconditions:
  - contact_message_id identifies one stored inbound stephen_dcx_contact_messages row.
  - the sender has already been resolved to a verified DCX user/contact method when possible.
- postconditions:
  - Returns None when the message does not contain a valid owner-owned topic reference.
  - Appends one user market-topic turn and one assistant turn when the message includes a valid
    #AI-style reference.
  - Marks the contact message as ready/completed with workflow metadata showing the routed topic.
  - Attempts to send the assistant response back on the same channel.
- side_effects:
  - may insert into stephen_dcx_market_topic_turns.
  - may update stephen_dcx_market_topics.updated_at_ts_ms.
  - may update stephen_dcx_contact_messages status/metadata.
  - may call Resend or Meta WhatsApp for the AI response.
- idempotent: true for the same source_contact_message_id because append deduplication reuses the
  existing topic turn pair.
- retry_safe: true for persistence; provider notification retries may duplicate external sends.
- async: false, blocking database/provider/LLM work for this MVP mini slice.
- idempotency_key: inbound_market_topic_reply:{contact_message_id}
- locks: append capability locks stephen_dcx_market_topics.id FOR UPDATE.
- contention strategy: duplicate provider webhooks converge through source_message_id checks.

NARRATIVE:
WHY this exists:
  Market topics are now private AI workspaces. A trader should be able to receive `#AI2` and then
  ask follow-up questions from the same real-world channels they use for trade chats.
WHEN TO USE it:
  Use it after the provider message has been persisted and attachments stored, before normal
  classification/routing.
WHEN NOT TO USE it:
  Do not use it for public forum comments or private trader-to-trader negotiation.
WHAT CAN GO WRONG:
  Traders can omit the reference, use a closed topic, send from an unverified address, or hit a
  provider/LLM delay while the webhook is open.
WHAT COMES NEXT:
  Move AI generation and same-channel response delivery to jobs once webhook latency needs harder
  production guarantees.

TESTS:
- route_dcx_inbound_contact_message_to_market_topic_if_applicable_test.py

ERRORS:
- API_DCX_INBOUND_MARKET_TOPIC_ROUTE_FAILED:
  suggested_action: allow the message to fall back to normal message processing after inspecting logs.
  common_causes: schema drift, database outage, append capability failure.
  recovery_steps: confirm topic id/reference, contact resolution, and database health.
  retry_safe: true.
  what_changed: contact message may already be stored; topic turns may have been appended.
  rollback_needed: false unless a duplicate topic turn was manually created.
  rollback_operation: delete duplicate stephen_dcx_market_topic_turns rows after operator review.

CODE:
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from messages.append_authenticated_dcx_user_market_topic_ai_chat_turn import (
    append_authenticated_dcx_user_market_topic_ai_chat_turn,
)
from messages.dcx_inbound_cross_surface_reference_text import (
    build_dcx_cross_surface_routed_message_text,
    extract_dcx_cross_surface_reference_code,
    read_dcx_cross_surface_reference_id,
)
from messages.send_dcx_market_topic_ai_turn_response_notification import (
    send_dcx_market_topic_ai_turn_response_notification,
)
from storage.db_config import DB_CONFIG


def route_dcx_inbound_contact_message_to_market_topic_if_applicable(
    contact_message_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    append_market_topic_turn: Callable[..., dict | None] | None = None,
    send_ai_response_notification: Callable[..., dict] | None = None,
) -> dict | None:
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = int(time.time() * 1000)

    try:
        message_context = _read_inbound_contact_message_market_topic_route_context(
            connect=connect,
            contact_message_id=contact_message_id,
        )
        if message_context is None:
            return None
        if message_context["user_id"] is None or message_context["source_contact_is_verified"] is not True:
            return None

        topic_reference_code = _extract_market_topic_reference_code(
            f"{message_context['message_subject']}\n{message_context['raw_text_content']}"
        )
        if topic_reference_code is None:
            return None
        market_topic_id = read_dcx_cross_surface_reference_id(
            reference_code=topic_reference_code,
            reference_prefix="AI",
        )
        if market_topic_id is None:
            return None

        topic_context = _read_referenced_market_topic_for_owner(
            connect=connect,
            market_topic_id=market_topic_id,
            owner_user_id=message_context["user_id"],
        )
        if topic_context is None:
            return None

        routed_message_text = build_dcx_cross_surface_routed_message_text(
            message_subject=message_context["message_subject"],
            message_text=message_context["raw_text_content"],
            reference_code=topic_reference_code,
            include_subject=message_context["channel_type"] == "email",
        )
        if routed_message_text == "":
            return None

        append_result = (append_market_topic_turn or append_authenticated_dcx_user_market_topic_ai_chat_turn)(
            authenticated_user_id=message_context["user_id"],
            market_topic_id=market_topic_id,
            user_turn_text=routed_message_text,
            preferred_language_code=message_context["preferred_language_code"],
            source_message_id=contact_message_id,
            source_channel_type=message_context["channel_type"],
            source_contact_method_id=message_context["contact_method_id"],
            source_route_reference_code=topic_reference_code,
            source_surface=message_context["channel_type"],
            connect_to_database=connect,
        )
        if append_result is None:
            return None

        notification_result = {"status": "skipped", "reason": "deduped_topic_turn"}
        if append_result.get("deduped") is not True:
            try:
                notification_result = (
                    send_ai_response_notification or send_dcx_market_topic_ai_turn_response_notification
                )(
                    market_topic_id=market_topic_id,
                    route_reference_code=topic_reference_code,
                    topic_title=topic_context["topic_title"],
                    channel_type=message_context["channel_type"],
                    recipient_handle=message_context["source_handle_normalized"],
                    assistant_turn_text=append_result["assistant_turn_text"],
                )
            except Exception as notification_error:
                notification_result = {
                    "status": "failed",
                    "error": str(notification_error),
                    "channel_type": message_context["channel_type"],
                }

        _mark_contact_message_as_market_topic_routed(
            connect=connect,
            contact_message_id=contact_message_id,
            market_topic_id=market_topic_id,
            topic_reference_code=topic_reference_code,
            append_result=append_result,
            notification_result=notification_result,
            now_ts_ms=now_ts_ms,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_INBOUND_MARKET_TOPIC_ROUTE_FAILED") from exc

    return {
        "routed": True,
        "market_topic_id": market_topic_id,
        "topic_reference_code": topic_reference_code,
        "user_turn_id": append_result["user_turn_id"],
        "assistant_turn_id": append_result["assistant_turn_id"],
        "notification_result": notification_result,
        "processing_status": "ready",
        "derivation_status": "completed",
    }


def _read_inbound_contact_message_market_topic_route_context(
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
                    message.source_handle_normalized,
                    message.message_subject,
                    message.raw_text_content,
                    message.message_metadata_json,
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
        "source_handle_normalized": row[4] or "",
        "message_subject": row[5] or "",
        "raw_text_content": row[6] or "",
        "source_contact_is_verified": (
            row[7].get("source_contact_is_verified") is True
            if isinstance(row[7], dict)
            else False
        ),
        "preferred_language_code": row[8] or "en",
    }


def _extract_market_topic_reference_code(text: str) -> str | None:
    return extract_dcx_cross_surface_reference_code(text=text, reference_prefix="AI")


def _read_referenced_market_topic_for_owner(
    connect: Callable[..., Any],
    market_topic_id: int,
    owner_user_id: int,
) -> dict | None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, topic_title, topic_status
                FROM stephen_dcx_market_topics
                WHERE id = %s
                  AND initiating_user_id = %s
                  AND topic_status = 'open'
                LIMIT 1
                """,
                (market_topic_id, owner_user_id),
            )
            row = cursor.fetchone()

    if row is None:
        return None
    return {
        "market_topic_id": row[0],
        "topic_title": row[1] or "",
        "topic_status": row[2],
    }


def _mark_contact_message_as_market_topic_routed(
    connect: Callable[..., Any],
    contact_message_id: int,
    market_topic_id: int,
    topic_reference_code: str,
    append_result: dict,
    notification_result: dict,
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
                    workflow_metadata_json = COALESCE(workflow_metadata_json, '{}'::jsonb) || %s::jsonb,
                    analysis_completed_at_ts_ms = %s,
                    updated_at_ts_ms = %s
                WHERE id = %s
                """,
                (
                    f"Routed to private AI chat {topic_reference_code}.",
                    f"Routed to private AI chat {topic_reference_code}.",
                    Json(
                        {
                            "market_topic_routing": {
                                "routed": True,
                                "market_topic_id": market_topic_id,
                                "topic_reference_code": topic_reference_code,
                                "user_turn_id": append_result.get("user_turn_id"),
                                "assistant_turn_id": append_result.get("assistant_turn_id"),
                                "deduped": append_result.get("deduped") is True,
                                "notification_result": notification_result,
                            }
                        }
                    ),
                    now_ts_ms,
                    now_ts_ms,
                    contact_message_id,
                ),
            )
