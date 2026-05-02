"""
CONTEXT:
This file normalizes Meta WhatsApp outbound message status webhooks for DCX.
It exists because the Meta messages API first returns an accepted provider message id, then later
sends webhook `statuses` that tell DCX whether that outbound message was sent, delivered, read, or
failed.

CONTRACT:
- preconditions:
  - webhook_payload is one verified parsed Meta WhatsApp webhook JSON object.
- postconditions:
  - Returns one list of canonical outbound status events, possibly empty.
- side_effects: []
- idempotent: true
- retry_safe: true
- async: false

NARRATIVE:
WHY this exists:
  Meta separates API acceptance from actual WhatsApp delivery. DCX needs those later statuses to
  debug and eventually display cross-surface notification health.
WHEN TO USE it:
  Use it after webhook signature verification and before updating outbound route metadata.
WHEN NOT TO USE it:
  Do not use it for inbound user messages; those are parsed by the inbound envelope reader.
WHAT CAN GO WRONG:
  Some webhook payloads contain only inbound messages and no statuses; that is normal.
WHAT COMES NEXT:
  The canonical events can update stephen_dcx_outbound_interaction_routes for delivery diagnostics.

TESTS:
- test_processes_meta_whatsapp_outbound_status_webhook_event

ERRORS:
- none

CODE:
"""

from __future__ import annotations

from typing import Any


def read_dcx_meta_whatsapp_outbound_status_events_from_webhook_payload(
    webhook_payload: dict,
) -> list[dict[str, Any]]:
    status_events: list[dict[str, Any]] = []

    for entry in webhook_payload.get("entry", []):
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []):
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            for status_payload in value.get("statuses", []):
                if not isinstance(status_payload, dict):
                    continue

                provider_message_id = (status_payload.get("id") or "").strip()
                provider_status = (status_payload.get("status") or "").strip().lower()
                if provider_message_id == "" or provider_status == "":
                    continue

                status_events.append(
                    {
                        "provider_message_id": provider_message_id,
                        "provider_status": provider_status,
                        "recipient_id": (status_payload.get("recipient_id") or "").strip() or None,
                        "status_timestamp_ms": _read_dcx_meta_whatsapp_status_timestamp_ms(
                            status_payload.get("timestamp")
                        ),
                        "conversation": status_payload.get("conversation")
                        if isinstance(status_payload.get("conversation"), dict)
                        else {},
                        "pricing": status_payload.get("pricing")
                        if isinstance(status_payload.get("pricing"), dict)
                        else {},
                        "errors": status_payload.get("errors")
                        if isinstance(status_payload.get("errors"), list)
                        else [],
                        "raw_status_payload_json": status_payload,
                    }
                )

    return status_events


def _read_dcx_meta_whatsapp_status_timestamp_ms(raw_timestamp: Any) -> int:
    if isinstance(raw_timestamp, str) and raw_timestamp.isdigit():
        return int(raw_timestamp) * 1000
    if isinstance(raw_timestamp, int):
        return raw_timestamp * 1000
    return 0
