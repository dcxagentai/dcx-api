"""
CONTEXT:
This file processes one verified Meta WhatsApp inbound webhook payload into canonical DCX messages.
It exists so incoming WhatsApp trader messages become stored, derived DCX contact-message rows with
one quiet provider read receipt instead of one extra acknowledgement bubble.
"""

from __future__ import annotations

from typing import Any, Callable

from apis.meta_whatsapp.read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload import (
    read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload,
)
from apis.meta_whatsapp.read_dcx_meta_whatsapp_outbound_status_events_from_webhook_payload import (
    read_dcx_meta_whatsapp_outbound_status_events_from_webhook_payload,
)
from apis.meta_whatsapp.read_dcx_meta_whatsapp_media_bytes import (
    read_dcx_meta_whatsapp_media_bytes,
)
from apis.meta_whatsapp.mark_dcx_meta_whatsapp_inbound_message_as_read import (
    mark_dcx_meta_whatsapp_inbound_message_as_read,
)
from messages.ingest_dcx_contact_message_from_inbound_envelope import (
    ingest_dcx_contact_message_from_inbound_envelope,
)
from messages.store_dcx_contact_message_provider_event import (
    store_dcx_contact_message_provider_event,
)
from messages.record_dcx_meta_whatsapp_outbound_status_event import (
    record_dcx_meta_whatsapp_outbound_status_event,
)

def process_dcx_meta_whatsapp_inbound_webhook_payload(
    webhook_payload: dict,
    store_provider_event: Callable[..., dict] | None = None,
    read_message_envelopes: Callable[[dict], list[dict]] | None = None,
    read_outbound_status_events: Callable[[dict], list[dict]] | None = None,
    record_outbound_status_event: Callable[[dict], dict] | None = None,
    read_media_bytes: Callable[[str], dict] | None = None,
    ingest_inbound_envelope: Callable[..., dict] | None = None,
    mark_whatsapp_message_as_read: Callable[..., dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - webhook_payload is one verified Meta WhatsApp webhook JSON object.
      postconditions:
        - Stores one provider-event row for the webhook payload.
        - Stores one canonical DCX message row per normalized inbound message envelope.
        - Downloads and stores supported media attachments when the inbound envelope references them.
        - Attempts one WhatsApp read receipt per inbound envelope.
      side_effects:
        - writes to stephen_dcx_contact_message_provider_events
        - writes to stephen_dcx_contact_messages
        - may mark inbound WhatsApp messages as read through Meta
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: meta_whatsapp_payload:{payload_hash}
      locks:
        - delegated to provider-event and message ingestion capabilities
      contention_strategy: duplicate webhook payloads converge through provider-event and provider-message id deduplication

    NARRATIVE:
      WHY this exists:
        - Traders should be able to send raw WhatsApp messages into DCX and see them become canonical
          stored messages immediately.
      WHEN TO USE it:
        - Use it only after the Meta webhook POST has been verified.
      WHEN NOT TO USE it:
        - Do not use it for the GET webhook handshake or outbound delivery-status events.
      WHAT CAN GO WRONG:
        - The payload may contain no inbound messages.
        - Message ingestion can fail for one or more envelopes.
        - The read-receipt request can fail without blocking message ingestion.
      WHAT COMES NEXT:
        - Media download, transcription, and richer trade classification can build on these stored rows.

    TESTS:
      - test_processes_meta_whatsapp_payload_into_stored_message_and_read_receipt
      - test_processes_meta_whatsapp_media_attachment_into_inbound_attachment_inputs
      - test_processes_meta_whatsapp_message_when_one_attachment_fetch_fails
      - test_marks_each_image_in_multi_image_whatsapp_burst_as_read_without_sending_text

    ERRORS:
      - API_DCX_META_WHATSAPP_INBOUND_PROCESS_FAILED:
          suggested_action: Retry after confirming the webhook payload is valid and the backend is healthy.
          common_causes:
            - malformed payload
            - provider-event store failure
            - message ingest failure
          recovery_steps:
            - Confirm the webhook payload shape.
            - Retry once the backend is stable.
          retry_safe: true

    CODE:
    """
    try:
        store_event = store_provider_event or store_dcx_contact_message_provider_event
        provider_event_result = store_event(
            provider_type="meta_whatsapp",
            channel_type="whatsapp",
            provider_event_type="whatsapp_message_webhook",
            raw_event_payload_json=webhook_payload,
            signature_verified=True,
            processing_status="processed",
        )
        message_envelopes = (
            read_message_envelopes or read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload
        )(webhook_payload)
        outbound_status_events = (
            read_outbound_status_events or read_dcx_meta_whatsapp_outbound_status_events_from_webhook_payload
        )(webhook_payload)
    except Exception as exc:
        raise RuntimeError("API_DCX_META_WHATSAPP_INBOUND_PROCESS_FAILED") from exc

    recorded_status_events: list[dict] = []
    failed_status_event_count = 0
    for status_event in outbound_status_events:
        try:
            recorded_status_events.append(
                (record_outbound_status_event or record_dcx_meta_whatsapp_outbound_status_event)(
                    status_event
                )
            )
        except Exception:
            failed_status_event_count += 1

    processed_messages: list[dict] = []
    for message_envelope in message_envelopes:
        read_receipt_status = "not_sent"
        should_mark_message_as_read = message_envelope.get("should_mark_read") is True
        if should_mark_message_as_read:
            try:
                (mark_whatsapp_message_as_read or mark_dcx_meta_whatsapp_inbound_message_as_read)(
                    provider_message_id=message_envelope["provider_message_id"],
                )
                read_receipt_status = "accepted"
            except Exception:
                read_receipt_status = "failed"

        try:
            attachment_inputs = []
            skipped_attachment_reads = []
            for attachment_index, attachment_descriptor in enumerate(
                message_envelope.get("attachment_descriptors", []),
                start=1,
            ):
                provider_media_id = attachment_descriptor.get("provider_media_id")
                if not isinstance(provider_media_id, str) or provider_media_id.strip() == "":
                    continue
                try:
                    media_payload = (read_media_bytes or read_dcx_meta_whatsapp_media_bytes)(provider_media_id)
                except Exception:
                    skipped_attachment_reads.append(
                        {
                            "index": attachment_index,
                            "provider_media_id": provider_media_id,
                            "original_filename": attachment_descriptor.get("original_filename"),
                            "error_code": "API_DCX_META_WHATSAPP_MEDIA_READ_FAILED",
                        }
                    )
                    continue
                attachment_inputs.append(
                    {
                        "original_filename": attachment_descriptor.get("original_filename"),
                        "content_type": attachment_descriptor.get("content_type") or media_payload.get("content_type"),
                        "file_bytes": media_payload["file_bytes"],
                        "provider_media_id": provider_media_id,
                    }
                )

            ingest_result = (ingest_inbound_envelope or ingest_dcx_contact_message_from_inbound_envelope)(
                provider_event_row_id=provider_event_result["provider_event_id"],
                provider_type="meta_whatsapp",
                channel_type="whatsapp",
                provider_message_id=message_envelope["provider_message_id"],
                source_handle=message_envelope["source_handle"],
                target_handle=message_envelope["target_handle"],
                message_format=message_envelope["message_format"],
                raw_text_content=message_envelope["raw_text_content"],
                received_at_ts_ms=message_envelope["received_at_ts_ms"],
                message_subject=message_envelope["message_subject"],
                message_metadata_json={
                    **(message_envelope["message_metadata_json"] or {}),
                    "meta_skipped_attachment_reads": skipped_attachment_reads,
                },
                attachment_inputs=attachment_inputs,
            )
        except Exception as exc:
            raise RuntimeError("API_DCX_META_WHATSAPP_INBOUND_PROCESS_FAILED") from exc

        processed_messages.append(
            {
                **ingest_result,
                "provider_message_id": message_envelope["provider_message_id"],
                "read_receipt_status": read_receipt_status,
                "acknowledgement_status": read_receipt_status,
            }
        )

    return {
        "status": "processed",
        "provider_event_id": provider_event_result["provider_event_id"],
        "processed_message_count": len(processed_messages),
        "outbound_status_event_count": len(outbound_status_events),
        "recorded_outbound_status_event_count": len(recorded_status_events),
        "failed_outbound_status_event_count": failed_status_event_count,
        "outbound_status_events": recorded_status_events,
        "messages": processed_messages,
    }
