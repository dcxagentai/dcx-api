"""
CONTEXT:
This file sends MVP interested-trade alerts when a confirmed and published trade overlaps with
another user's saved material interests.
It exists to demonstrate the investor-video beat where a trader interested in aluminum is notified
when a relevant DCX trade becomes available.

CONTRACT:
preconditions:
- trade_id identifies one trade with a current version.
- The trade must be confirmed/open and have an active shareable or public publication before any
  external interested-user alert is sent.
postconditions:
- Finds users whose selected material interests overlap with the trade material.
- Excludes the trade owner.
- Sends at most one external alert per trade, recipient, and material key.
- Records sent, skipped, and failed attempts in stephen_dcx_trade_interest_alert_deliveries.
side_effects:
- may send email through Resend
- may send WhatsApp through Meta
- mutates stephen_dcx_trade_interest_alert_deliveries
idempotent: true
retry_safe: true
async: false
idempotency_key: trade_interest_alert:{trade_id}:{recipient_user_id}:{material_key}
locks: unique index on stephen_dcx_trade_interest_alert_deliveries(trade_id, recipient_user_id, material_key)
contention_strategy: concurrent callers race on the delivery uniqueness constraint; one sends, the rest skip duplicates.

NARRATIVE:
WHY this exists:
  The MVP can now structure trades and route chats. This slice adds the missing discovery signal:
  users who opted into a commodity/material interest can hear about newly available confirmed deals.
WHEN TO USE it:
  Call it after a trade is confirmed or after a trade is published/shareable. The function re-checks
  eligibility so either trigger is safe.
WHEN NOT TO USE it:
  Do not call it for raw AI extractions, incomplete trade candidates, or private unconfirmed drafts.
WHAT CAN GO WRONG:
  A trade may not be eligible yet, the material can fail to map to a simple interest key, recipients
  may have no usable channel, or providers can reject delivery.
WHAT COMES NEXT:
  Move provider sends into a durable queue, add WhatsApp template support for the >24h window, and
  later add real matching dimensions such as side, geography, incoterm, price, KYC, and counterparty rules.

TESTS:
- send_dcx_trade_interest_alert_notifications_test.py::test_sends_email_alert_to_matching_interested_user
- send_dcx_trade_interest_alert_notifications_test.py::test_skips_unconfirmed_trade

ERRORS:
- API_DCX_TRADE_INTEREST_ALERT_READ_FAILED: inspect database health and trade/publication rows.
- API_DCX_TRADE_INTEREST_ALERT_SEND_FAILED: alert send failed after a delivery attempt row was created.

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
from messages.build_dcx_trade_interest_alert_notification_text import (
    build_dcx_trade_interest_alert_notification_text,
)
from messages.read_dcx_trade_interest_material_key import (
    read_dcx_trade_interest_material_key,
)
from storage.db_config import DB_CONFIG


def send_dcx_trade_interest_alert_notifications(
    trade_id: int,
    trigger_source: str,
    connect_to_database: Callable[..., Any] | None = None,
    send_email_notification: Callable[..., dict] | None = None,
    send_whatsapp_notification: Callable[..., dict] | None = None,
) -> dict:
    if not isinstance(trade_id, int) or trade_id <= 0:
        return {"status": "skipped", "reason": "invalid_trade_id", "sent_count": 0}

    connect = connect_to_database or psycopg2.connect
    email_sender = send_email_notification or send_dcx_email_message_workflow_outcome_notification
    whatsapp_sender = send_whatsapp_notification or send_dcx_whatsapp_message_workflow_outcome_notification

    try:
        alert_context = _read_trade_interest_alert_context(connect=connect, trade_id=trade_id)
    except Exception as exc:
        raise RuntimeError("API_DCX_TRADE_INTEREST_ALERT_READ_FAILED") from exc

    if alert_context is None:
        return {"status": "skipped", "reason": "trade_not_found", "sent_count": 0}
    if not alert_context["is_alert_eligible"]:
        return {"status": "skipped", "reason": "trade_not_alert_eligible", "sent_count": 0}

    material_key = read_dcx_trade_interest_material_key(
        alert_context["trade_snapshot"].get("normalized_material_name"),
        alert_context["material_options"],
    )
    if material_key is None:
        return {"status": "skipped", "reason": "material_not_matched", "sent_count": 0}

    recipients = _read_interested_trade_alert_recipients(
        connect=connect,
        owner_user_id=alert_context["owner_user_id"],
        material_key=material_key,
    )
    if not recipients:
        return {
            "status": "skipped",
            "reason": "no_interested_recipients",
            "sent_count": 0,
            "material_key": material_key,
        }

    sent_count = 0
    skipped_count = 0
    failed_count = 0
    for recipient in recipients:
        delivery_result = _send_one_trade_interest_alert(
            connect=connect,
            alert_context=alert_context,
            recipient=recipient,
            material_key=material_key,
            trigger_source=trigger_source,
            email_sender=email_sender,
            whatsapp_sender=whatsapp_sender,
        )
        if delivery_result["status"] == "sent":
            sent_count += 1
        elif delivery_result["status"] == "failed":
            failed_count += 1
        else:
            skipped_count += 1

    return {
        "status": "completed",
        "material_key": material_key,
        "sent_count": sent_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
    }


def _read_trade_interest_alert_context(connect: Callable[..., Any], trade_id: int) -> dict | None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    trade.id,
                    trade.initiating_user_id,
                    trade.visibility_status,
                    trade_version.trade_confirmation_status,
                    trade_version.trade_status,
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
                    publication.id,
                    publication.visibility_status,
                    publication.publication_status
                FROM stephen_dcx_trades trade
                INNER JOIN stephen_dcx_trade_versions trade_version
                  ON trade_version.id = trade.current_version_id
                LEFT JOIN stephen_dcx_trade_publications publication
                  ON publication.trade_id = trade.id
                 AND publication.publication_status = 'active'
                 AND publication.visibility_status IN ('shareable', 'public')
                WHERE trade.id = %s
                LIMIT 1
                """,
                (trade_id,),
            )
            trade_row = cursor.fetchone()
            if trade_row is None:
                return None

            cursor.execute(
                """
                SELECT material_key, synonyms_json
                FROM stephen_dcx_trade_interest_material_options
                WHERE is_active = TRUE
                ORDER BY sort_order ASC, display_label ASC
                """
            )
            material_option_rows = cursor.fetchall()

    is_confirmed_open = trade_row[3] == "confirmed" and trade_row[4] == "open"
    has_active_publication = trade_row[15] is not None and trade_row[17] == "active"
    return {
        "trade_id": trade_row[0],
        "owner_user_id": trade_row[1],
        "trade_publication_id": trade_row[15],
        "is_alert_eligible": is_confirmed_open and has_active_publication,
        "trade_snapshot": {
            "trade_summary_text": trade_row[5] or "",
            "normalized_trade_side": trade_row[6] or "",
            "normalized_material_name": trade_row[7] or "",
            "normalized_quantity_value": float(trade_row[8]) if trade_row[8] is not None else None,
            "normalized_quantity_unit": trade_row[9] or "",
            "normalized_price_value": float(trade_row[10]) if trade_row[10] is not None else None,
            "normalized_price_unit_basis": trade_row[11] or "",
            "normalized_currency_code": trade_row[12] or "",
            "normalized_origin_location": trade_row[13] or "",
            "normalized_destination_location": trade_row[14] or "",
        },
        "material_options": [
            {
                "material_key": material_option_row[0],
                "synonyms": material_option_row[1] if isinstance(material_option_row[1], list) else [],
            }
            for material_option_row in material_option_rows
        ],
    }


def _read_interested_trade_alert_recipients(
    connect: Callable[..., Any],
    owner_user_id: int,
    material_key: str,
) -> list[dict]:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    interested_user.id,
                    COALESCE(interested_user.default_interaction_channel, 'app_only')
                FROM stephen_dcx_user_trade_interest_materials interest
                INNER JOIN stephen_dcx_users interested_user
                  ON interested_user.id = interest.user_id
                WHERE interest.material_key = %s
                  AND interest.user_id <> %s
                  AND interested_user.account_status = 'confirmed'
                ORDER BY interested_user.id ASC
                """,
                (
                    material_key,
                    owner_user_id,
                ),
            )
            recipient_rows = cursor.fetchall()

    return [
        {
            "recipient_user_id": recipient_row[0],
            "default_interaction_channel": recipient_row[1],
        }
        for recipient_row in recipient_rows
    ]


def _send_one_trade_interest_alert(
    connect: Callable[..., Any],
    alert_context: dict,
    recipient: dict,
    material_key: str,
    trigger_source: str,
    email_sender: Callable[..., dict],
    whatsapp_sender: Callable[..., dict],
) -> dict:
    route = _resolve_trade_interest_alert_route(
        connect=connect,
        recipient_user_id=recipient["recipient_user_id"],
        preferred_default_channel=recipient["default_interaction_channel"],
    )
    delivery_id = _create_trade_interest_alert_delivery(
        connect=connect,
        alert_context=alert_context,
        recipient_user_id=recipient["recipient_user_id"],
        material_key=material_key,
        channel_type=route["channel"],
        trigger_source=trigger_source,
    )
    if delivery_id is None:
        return {"status": "skipped", "reason": "duplicate"}
    if route["channel"] == "app_only":
        _mark_trade_interest_alert_delivery(
            connect=connect,
            delivery_id=delivery_id,
            delivery_status="skipped",
            provider_type=None,
            provider_message_id=None,
            delivery_error=route["reason"],
            provider_result={},
        )
        return {"status": "skipped", "reason": route["reason"]}

    message_text = build_dcx_trade_interest_alert_notification_text(
        trade_publication_id=alert_context["trade_publication_id"],
        trade_snapshot=alert_context["trade_snapshot"],
    )
    try:
        if route["channel"] == "email":
            provider_result = email_sender(
                recipient_email=route["destination"],
                subject=f"DCX: {alert_context['trade_snapshot'].get('normalized_material_name') or 'trade'} matching your interests",
                message_text=message_text,
            )
            provider_type = "resend"
        elif route["channel"] == "whatsapp":
            provider_result = whatsapp_sender(
                phone_e164=route["destination"],
                message_text=message_text,
            )
            provider_type = "meta_whatsapp"
        else:
            provider_result = {}
            provider_type = None
            raise RuntimeError("unsupported_route")

        provider_message_id = str(provider_result.get("provider_message_id") or "").strip()
        if provider_message_id == "":
            provider_message_id = f"dcx_trade_interest_alert_{delivery_id}_{int(time.time() * 1000)}"
        _mark_trade_interest_alert_delivery(
            connect=connect,
            delivery_id=delivery_id,
            delivery_status="sent",
            provider_type=provider_type,
            provider_message_id=provider_message_id,
            delivery_error="",
            provider_result=provider_result,
        )
        return {"status": "sent", "channel": route["channel"], "provider_message_id": provider_message_id}
    except Exception as exc:
        _mark_trade_interest_alert_delivery(
            connect=connect,
            delivery_id=delivery_id,
            delivery_status="failed",
            provider_type=None,
            provider_message_id=None,
            delivery_error=f"{type(exc).__name__}: {exc}",
            provider_result={},
        )
        return {"status": "failed", "reason": "provider_send_failed"}


def _resolve_trade_interest_alert_route(
    connect: Callable[..., Any],
    recipient_user_id: int,
    preferred_default_channel: str,
) -> dict:
    selected_channel = preferred_default_channel.strip().lower() if isinstance(preferred_default_channel, str) else "app_only"
    if selected_channel == "email":
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, normalized_value
                    FROM stephen_dcx_users_contact_methods
                    WHERE user_id = %s
                      AND contact_type = 'email'
                      AND is_active = TRUE
                      AND is_verified = TRUE
                      AND is_notification_enabled = TRUE
                    ORDER BY is_primary DESC, id ASC
                    LIMIT 1
                    """,
                    (recipient_user_id,),
                )
                contact_row = cursor.fetchone()
        if contact_row is not None:
            return {"channel": "email", "destination": contact_row[1], "reason": "email_route"}

    if selected_channel == "whatsapp":
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
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
                    ORDER BY cm.is_primary DESC, cm.id ASC
                    LIMIT 1
                    """,
                    (recipient_user_id,),
                )
                contact_row = cursor.fetchone()
        if contact_row is not None:
            return {"channel": "whatsapp", "destination": contact_row[1], "reason": "whatsapp_route"}

    return {"channel": "app_only", "destination": None, "reason": "no_external_route"}


def _create_trade_interest_alert_delivery(
    connect: Callable[..., Any],
    alert_context: dict,
    recipient_user_id: int,
    material_key: str,
    channel_type: str,
    trigger_source: str,
) -> int | None:
    now_ts_ms = int(time.time() * 1000)
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO stephen_dcx_trade_interest_alert_deliveries (
                    trade_id,
                    trade_publication_id,
                    recipient_user_id,
                    material_key,
                    channel_type,
                    delivery_status,
                    delivery_metadata_json,
                    created_at_ts_ms,
                    updated_at_ts_ms
                )
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s)
                ON CONFLICT (trade_id, recipient_user_id, material_key) DO NOTHING
                RETURNING id
                """,
                (
                    alert_context["trade_id"],
                    alert_context["trade_publication_id"],
                    recipient_user_id,
                    material_key,
                    channel_type,
                    Json({"trigger_source": trigger_source}),
                    now_ts_ms,
                    now_ts_ms,
                ),
            )
            delivery_row = cursor.fetchone()
    if delivery_row is None:
        return None
    return delivery_row[0]


def _mark_trade_interest_alert_delivery(
    connect: Callable[..., Any],
    delivery_id: int,
    delivery_status: str,
    provider_type: str | None,
    provider_message_id: str | None,
    delivery_error: str,
    provider_result: dict,
) -> None:
    now_ts_ms = int(time.time() * 1000)
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE stephen_dcx_trade_interest_alert_deliveries
                SET
                    delivery_status = %s,
                    provider_type = %s,
                    provider_message_id = %s,
                    delivery_error = %s,
                    delivery_metadata_json = delivery_metadata_json || %s::jsonb,
                    updated_at_ts_ms = %s
                WHERE id = %s
                """,
                (
                    delivery_status,
                    provider_type,
                    provider_message_id,
                    delivery_error,
                    Json({"provider_result": provider_result}),
                    now_ts_ms,
                    delivery_id,
                ),
            )
