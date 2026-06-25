"""
CONTEXT:
This file sends one cross-surface notification for a newly appended private trade-thread message.
It exists so the canonical private trade conversation can stay in DCX while each trader receives
new-message alerts through their current preferred surface: app only, email, or WhatsApp.

CONTRACT:
- preconditions:
  - trade_thread_id identifies one private trade thread.
  - sender_user_id and recipient_user_id are the two participants in that thread.
  - message_text is the canonical newly appended message text.
- postconditions:
  - Sends at most one external notification to the recipient.
  - Records provider delivery metadata in stephen_dcx_outbound_interaction_routes when an external provider accepts it.
  - Returns a small delivery result describing whether the notification was sent or skipped.
- side_effects:
  - may call Resend to send email.
  - may call Meta WhatsApp to send a text message.
  - may insert one stephen_dcx_outbound_interaction_routes row.
- idempotent: false.
- retry_safe: false unless the caller accepts duplicate notifications.
- async: false, blocking provider send.
- idempotency_key: not implemented for MVP notification fan-out.
- locks: none.
- contention strategy: this is intentionally best-effort fan-out after the canonical message save.

NARRATIVE:
WHY this exists:
  Private trade chats now have a single durable web-app conversation, but real traders will reply
  from wherever they are already working. This file is the notification bridge: it tells the other
  trader there is a new message and gives them the thread reference code needed for email/WhatsApp
  continuation.
WHEN TO USE it:
  Use it after a trade-thread message has been saved by the app, email, or WhatsApp.
WHEN NOT TO USE it:
  Do not use it before the canonical message insert commits. Do not use it for public forum posts
  or market-topic AI chat turns.
WHAT CAN GO WRONG:
  The recipient may not have a usable verified email or WhatsApp contact. Provider sends can fail.
  Missing app base URL configuration can produce a wrong link.
WHAT COMES NEXT:
  Add richer per-thread routing controls and provider reply-id correlation. For MVP, explicit
  #C-style references keep routing legible and safe.

TESTS:
- Manual MVP smoke: set user B default to email, user A posts in a trade chat, B receives one email
  with the thread reference and clean app link.
- Manual MVP smoke: set user B default to WhatsApp, user A posts in a trade chat, B receives one
  WhatsApp text with the thread reference and clean app link.

ERRORS:
- API_DCX_TRADE_THREAD_NOTIFICATION_READ_FAILED:
  suggested_action: inspect database connectivity and thread participant rows.
  common_causes: schema drift, missing thread row, database outage.
  recovery_steps: refresh the thread detail and retry after database health is restored.
  retry_safe: true.
- API_DCX_TRADE_THREAD_NOTIFICATION_SEND_FAILED:
  suggested_action: keep the chat message saved and retry notification only if duplicate delivery is acceptable.
  common_causes: Resend/Meta outage, invalid provider configuration, missing contact method.
  recovery_steps: inspect provider logs and recipient contact-method rows.
  retry_safe: false.
  what_changed: the canonical chat message was already saved by the caller.
  rollback_needed: false.
  rollback_operation: none.

CODE:
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from apis.meta_whatsapp.send_dcx_whatsapp_message_workflow_outcome_notification import (
    send_dcx_whatsapp_message_workflow_outcome_notification,
)
from emails.transactional.send_dcx_email_message_workflow_outcome_notification import (
    send_dcx_email_message_workflow_outcome_notification,
)
from storage.db_config import DB_CONFIG
from users.account_phone.dcx_whatsapp_phone_link_challenge_support import read_dcx_app_base_url


def send_dcx_trade_thread_message_notification(
    trade_thread_id: int,
    sender_user_id: int,
    recipient_user_id: int,
    message_text: str,
    source_trade_thread_message_id: int | None = None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    normalized_message_text = message_text.strip() if isinstance(message_text, str) else ""
    if normalized_message_text == "":
        return {"status": "skipped", "reason": "empty_message"}

    connect = connect_to_database or psycopg2.connect
    notification_context = _read_trade_thread_notification_context(
        connect=connect,
        trade_thread_id=trade_thread_id,
        sender_user_id=sender_user_id,
        recipient_user_id=recipient_user_id,
    )
    if notification_context is None:
        return {"status": "skipped", "reason": "thread_or_participant_not_found"}

    route = _resolve_trade_thread_notification_route(
        connect=connect,
        trade_thread_id=trade_thread_id,
        recipient_user_id=recipient_user_id,
        preferred_default_channel=notification_context["recipient_default_interaction_channel"],
    )
    if route["channel"] == "app_only":
        return {"status": "skipped", "reason": route["reason"], "channel": "app_only"}

    try:
        if route["channel"] == "email":
            provider_result = send_dcx_email_message_workflow_outcome_notification(
                recipient_email=route["destination"],
                subject=f"DCX trade chat {notification_context['thread_reference_code']}",
                message_text=_build_trade_thread_notification_text(
                    notification_context=notification_context,
                    message_text=normalized_message_text,
                ),
            )
            provider_type = "resend"
        elif route["channel"] == "whatsapp":
            provider_result = send_dcx_whatsapp_message_workflow_outcome_notification(
                phone_e164=route["destination"],
                message_text=_build_trade_thread_notification_text(
                    notification_context=notification_context,
                    message_text=normalized_message_text,
                ),
            )
            provider_type = "meta_whatsapp"
        else:
            return {"status": "skipped", "reason": "unsupported_route", "channel": route["channel"]}

        provider_message_id = str(provider_result.get("provider_message_id") or "").strip()
        if provider_message_id == "":
            provider_message_id = f"dcx_trade_thread_notification_{trade_thread_id}_{recipient_user_id}_{int(time.time() * 1000)}"

        _record_trade_thread_notification_route(
            connect=connect,
            provider_type=provider_type,
            provider_message_id=provider_message_id,
            recipient_user_id=recipient_user_id,
            channel_type=route["channel"],
            trade_thread_id=trade_thread_id,
            route_reference_code=notification_context["thread_reference_code"],
            source_trade_thread_message_id=source_trade_thread_message_id,
            provider_result=provider_result,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_TRADE_THREAD_NOTIFICATION_SEND_FAILED") from exc

    return {
        "status": "sent",
        "channel": route["channel"],
        "provider_type": provider_type,
        "provider_message_id": provider_message_id,
    }


def upsert_dcx_trade_thread_participant_route(
    trade_thread_id: int,
    user_id: int,
    current_route_channel: str,
    current_route_contact_method_id: int | None,
    route_source: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> None:
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = int(time.time() * 1000)
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stephen_dcx_trade_thread_participant_routes (
                    trade_thread_id,
                    user_id,
                    current_route_channel,
                    current_route_contact_method_id,
                    route_source,
                    route_metadata_json,
                    created_at_ts_ms,
                    updated_at_ts_ms
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade_thread_id, user_id)
                DO UPDATE
                SET
                    current_route_channel = EXCLUDED.current_route_channel,
                    current_route_contact_method_id = EXCLUDED.current_route_contact_method_id,
                    route_source = EXCLUDED.route_source,
                    updated_at_ts_ms = EXCLUDED.updated_at_ts_ms
                """,
                (
                    trade_thread_id,
                    user_id,
                    current_route_channel,
                    current_route_contact_method_id,
                    route_source,
                    Json({}),
                    now_ts_ms,
                    now_ts_ms,
                ),
            )


def _read_trade_thread_notification_context(
    connect: Callable[..., Any],
    trade_thread_id: int,
    sender_user_id: int,
    recipient_user_id: int,
) -> dict | None:
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        thread.id,
                        thread.thread_reference_code,
                        thread.owner_user_id,
                        thread.counterparty_user_id,
                        COALESCE(recipient_user.default_interaction_channel, 'app_only'),
                        CASE
                          WHEN sender_user.public_identity_mode = 'handle' AND NULLIF(sender_user.public_handle, '') IS NOT NULL THEN '@' || sender_user.public_handle
                          WHEN NULLIF(sender_user.public_display_name, '') IS NOT NULL THEN sender_user.public_display_name
                          WHEN NULLIF(sender_user.public_handle, '') IS NOT NULL THEN '@' || sender_user.public_handle
                          ELSE 'Trader #' || sender_user.id::text
                        END AS sender_public_identity_label,
                        trade_version.trade_summary_text
                    FROM stephen_dcx_trade_threads thread
                    INNER JOIN stephen_dcx_users sender_user
                      ON sender_user.id = %s
                    INNER JOIN stephen_dcx_users recipient_user
                      ON recipient_user.id = %s
                    INNER JOIN stephen_dcx_trades trade
                      ON trade.id = thread.trade_id
                    INNER JOIN stephen_dcx_trade_versions trade_version
                      ON trade_version.id = trade.current_version_id
                    WHERE thread.id = %s
                      AND thread.thread_status = 'open'
                      AND (
                        (thread.owner_user_id = %s AND thread.counterparty_user_id = %s)
                        OR (thread.owner_user_id = %s AND thread.counterparty_user_id = %s)
                      )
                    LIMIT 1
                    """,
                    (
                        sender_user_id,
                        recipient_user_id,
                        trade_thread_id,
                        sender_user_id,
                        recipient_user_id,
                        recipient_user_id,
                        sender_user_id,
                    ),
                )
                row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError("API_DCX_TRADE_THREAD_NOTIFICATION_READ_FAILED") from exc

    if row is None:
        return None

    return {
        "trade_thread_id": row[0],
        "thread_reference_code": row[1],
        "owner_user_id": row[2],
        "counterparty_user_id": row[3],
        "recipient_default_interaction_channel": row[4],
        "sender_public_identity_label": row[5],
        "trade_summary_text": row[6],
    }


def _resolve_trade_thread_notification_route(
    connect: Callable[..., Any],
    trade_thread_id: int,
    recipient_user_id: int,
    preferred_default_channel: str,
) -> dict:
    normalized_default_channel = (
        preferred_default_channel.strip().lower()
        if isinstance(preferred_default_channel, str)
        else "app_only"
    )
    if normalized_default_channel not in {"app_only", "email", "whatsapp"}:
        normalized_default_channel = "app_only"

    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT current_route_channel, current_route_contact_method_id
                FROM stephen_dcx_trade_thread_participant_routes
                WHERE trade_thread_id = %s
                  AND user_id = %s
                LIMIT 1
                """,
                (trade_thread_id, recipient_user_id),
            )
            route_row = cursor.fetchone()

            selected_channel = route_row[0] if route_row is not None else normalized_default_channel
            selected_contact_method_id = route_row[1] if route_row is not None else None

            if selected_channel == "email":
                contact_row = _read_email_notification_contact_row(
                    cursor=cursor,
                    recipient_user_id=recipient_user_id,
                    selected_contact_method_id=selected_contact_method_id,
                )
                if contact_row is not None:
                    return {
                        "channel": "email",
                        "contact_method_id": contact_row[0],
                        "destination": contact_row[1],
                        "reason": "email_route",
                    }

            if selected_channel == "whatsapp":
                contact_row = _read_whatsapp_notification_contact_row(
                    cursor=cursor,
                    recipient_user_id=recipient_user_id,
                    selected_contact_method_id=selected_contact_method_id,
                )
                if contact_row is not None:
                    return {
                        "channel": "whatsapp",
                        "contact_method_id": contact_row[0],
                        "destination": contact_row[1],
                        "reason": "whatsapp_route",
                    }

    return {"channel": "app_only", "contact_method_id": None, "destination": None, "reason": "no_external_route"}


def _read_email_notification_contact_row(cursor: Any, recipient_user_id: int, selected_contact_method_id: int | None) -> tuple | None:
    cursor.execute(
        """
        SELECT id, normalized_value
        FROM stephen_dcx_users_contact_methods
        WHERE user_id = %s
          AND contact_type = 'email'
          AND is_active = TRUE
          AND is_verified = TRUE
          AND is_notification_enabled = TRUE
          AND (%s IS NULL OR id = %s)
        ORDER BY is_primary DESC, id ASC
        LIMIT 1
        """,
        (recipient_user_id, selected_contact_method_id, selected_contact_method_id),
    )
    return cursor.fetchone()


def _read_whatsapp_notification_contact_row(cursor: Any, recipient_user_id: int, selected_contact_method_id: int | None) -> tuple | None:
    cursor.execute(
        """
        SELECT cm.id, cm.normalized_value
        FROM stephen_dcx_users_contact_methods cm
        INNER JOIN stephen_dcx_user_auth_identities identity
          ON identity.contact_method_id = cm.id
         AND identity.provider_type = 'whatsapp'
        WHERE cm.user_id = %s
          AND cm.contact_type = 'phone'
          AND cm.is_active = TRUE
          AND cm.is_verified = TRUE
          AND (%s IS NULL OR cm.id = %s)
        ORDER BY cm.is_primary DESC, cm.id ASC
        LIMIT 1
        """,
        (recipient_user_id, selected_contact_method_id, selected_contact_method_id),
    )
    return cursor.fetchone()


def _build_trade_thread_notification_text(notification_context: dict, message_text: str) -> str:
    app_thread_url = f"{read_dcx_app_base_url().rstrip('/')}/trades/chats/{notification_context['trade_thread_id']}"
    preview_text = message_text if len(message_text) <= 500 else f"{message_text[:497]}..."
    return "\n\n".join(
        [
            f"New DCX trade chat message in {notification_context['thread_reference_code']}.",
            f"From {notification_context['sender_public_identity_label']}: {preview_text}",
            f"Open in DCX: {app_thread_url}",
            f"Reply with #{notification_context['thread_reference_code']} followed by your message.",
        ]
    )


def _record_trade_thread_notification_route(
    connect: Callable[..., Any],
    provider_type: str,
    provider_message_id: str,
    recipient_user_id: int,
    channel_type: str,
    trade_thread_id: int,
    route_reference_code: str,
    source_trade_thread_message_id: int | None,
    provider_result: dict,
) -> None:
    now_ts_ms = int(time.time() * 1000)
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stephen_dcx_outbound_interaction_routes (
                    provider_type,
                    provider_message_id,
                    recipient_user_id,
                    route_kind,
                    route_id,
                    channel_type,
                    route_metadata_json,
                    created_at_ts_ms,
                    trade_thread_id,
                    route_channel,
                    route_reference_code
                )
                VALUES (%s, %s, %s, 'trade_thread', %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (provider_type, provider_message_id)
                DO NOTHING
                """,
                (
                    provider_type,
                    provider_message_id,
                    recipient_user_id,
                    trade_thread_id,
                    channel_type,
                    Json(
                        {
                            "source_trade_thread_message_id": source_trade_thread_message_id,
                            "provider_result": provider_result,
                        }
                    ),
                    now_ts_ms,
                    trade_thread_id,
                    channel_type,
                    route_reference_code,
                ),
            )
