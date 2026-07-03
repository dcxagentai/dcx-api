"""
CONTEXT:
This file records one Meta WhatsApp outbound delivery status against a previously stored DCX
outbound interaction route.
It exists so DCX can distinguish "Meta accepted our send request" from "WhatsApp delivered/read it"
or "Meta later failed delivery with an error".

CONTRACT:
- preconditions:
  - status_event contains a Meta WhatsApp provider_message_id and provider_status.
  - stephen_dcx_outbound_interaction_routes may contain a row for that provider message id.
- postconditions:
  - If an outbound route row exists, updates route_metadata_json with latest_provider_status,
    latest_provider_status_at_ts_ms, latest_provider_error, and a bounded whatsapp_status_events list.
  - Returns whether a route row was matched.
- side_effects:
  - may update one stephen_dcx_outbound_interaction_routes row.
- idempotent: true for repeated identical provider status payloads, with a bounded diagnostic list.
- retry_safe: true
- async: false
- idempotency_key: meta_whatsapp_status:{provider_message_id}:{provider_status}:{status_timestamp_ms}
- locks:
  - row-level lock on the matching outbound route row through UPDATE.
- contention_strategy: concurrent status webhooks converge by overwriting latest status and appending
  bounded diagnostic events.

NARRATIVE:
WHY this exists:
  Trade-chat WhatsApp notifications can be accepted by the Graph API and still fail later. This
  recorder gives us concrete provider status evidence without adding a new table.
WHEN TO USE it:
  Use it from the verified Meta WhatsApp webhook processor for every `statuses` payload.
WHEN NOT TO USE it:
  Do not use it for inbound WhatsApp user messages or Resend email events.
WHAT CAN GO WRONG:
  The outbound row may not exist if the status is for another WhatsApp message type or an older send.
WHAT COMES NEXT:
  The same metadata can power admin diagnostics or user-facing delivery indicators later.

TESTS:
- test_processes_meta_whatsapp_outbound_status_webhook_event

ERRORS:
- API_DCX_META_WHATSAPP_OUTBOUND_STATUS_RECORD_FAILED:
  suggested_action: retry the webhook event after confirming database health.
  common_causes: database unavailable, malformed status event.
  recovery_steps: inspect stephen_dcx_outbound_interaction_routes by provider_message_id.
  retry_safe: true.
  what_changed: unknown if the transaction failed mid-update.
  rollback_needed: false.
  rollback_operation: none.

CODE:
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from storage.db_config import DB_CONFIG


def record_dcx_meta_whatsapp_outbound_status_event(
    status_event: dict[str, Any],
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    provider_message_id = str(status_event.get("provider_message_id") or "").strip()
    provider_status = str(status_event.get("provider_status") or "").strip().lower()
    if provider_message_id == "" or provider_status == "":
        return {"status": "skipped", "reason": "missing_provider_message_id_or_status"}

    event_timestamp_ms = status_event.get("status_timestamp_ms")
    if not isinstance(event_timestamp_ms, int) or event_timestamp_ms <= 0:
        event_timestamp_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()

    latest_provider_error = None
    errors = status_event.get("errors")
    if isinstance(errors, list) and len(errors) > 0 and isinstance(errors[0], dict):
        latest_provider_error = errors[0]

    diagnostic_event = {
        "provider_status": provider_status,
        "status_timestamp_ms": event_timestamp_ms,
        "recipient_id": status_event.get("recipient_id"),
        "errors": errors if isinstance(errors, list) else [],
        "conversation": status_event.get("conversation")
        if isinstance(status_event.get("conversation"), dict)
        else {},
        "pricing": status_event.get("pricing") if isinstance(status_event.get("pricing"), dict) else {},
    }

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE stephen_dcx_outbound_interaction_routes
                    SET
                        route_metadata_json = jsonb_set(
                            route_metadata_json
                            || jsonb_build_object(
                                'latest_provider_status', %s,
                                'latest_provider_status_at_ts_ms', %s,
                                'latest_provider_error', %s::jsonb
                            ),
                            '{whatsapp_status_events}',
                            (
                                SELECT jsonb_agg(event_item)
                                FROM (
                                    SELECT event_item
                                    FROM jsonb_array_elements(
                                        COALESCE(route_metadata_json->'whatsapp_status_events', '[]'::jsonb)
                                        || %s::jsonb
                                    ) WITH ORDINALITY AS appended_events(event_item, event_ordinal)
                                    ORDER BY event_ordinal DESC
                                    LIMIT 10
                                ) latest_events
                            ),
                            true
                        ),
                        updated_at_ts_ms = %s
                    WHERE provider_type = 'meta_whatsapp'
                      AND provider_message_id = %s
                    RETURNING id, trade_thread_id, recipient_user_id
                    """,
                    (
                        provider_status,
                        event_timestamp_ms,
                        Json(latest_provider_error),
                        Json([diagnostic_event]),
                        now_ts_ms,
                        provider_message_id,
                    ),
                )
                matched_row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError("API_DCX_META_WHATSAPP_OUTBOUND_STATUS_RECORD_FAILED") from exc

    if matched_row is None:
        return {
            "status": "unmatched",
            "provider_message_id": provider_message_id,
            "provider_status": provider_status,
        }

    return {
        "status": "recorded",
        "outbound_route_id": matched_row[0],
        "trade_thread_id": matched_row[1],
        "recipient_user_id": matched_row[2],
        "provider_message_id": provider_message_id,
        "provider_status": provider_status,
        "recorded_at_ts_ms": now_ts_ms,
    }


def _read_current_timestamp_ms() -> int:
    return int(time.time() * 1000)
