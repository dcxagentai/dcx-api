"""
CONTEXT:
This file processes one verified Meta WhatsApp inbound webhook payload into canonical DCX messages.
It exists so incoming WhatsApp trader messages become stored, derived DCX contact-message rows with
one immediate WhatsApp acknowledgement.
"""

from __future__ import annotations

from typing import Any, Callable

from apis.meta_whatsapp.read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload import (
    read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload,
)
from apis.meta_whatsapp.read_dcx_meta_whatsapp_media_bytes import (
    read_dcx_meta_whatsapp_media_bytes,
)
from apis.meta_whatsapp.send_dcx_whatsapp_text_message import send_dcx_whatsapp_text_message
from messages.ingest_dcx_contact_message_from_inbound_envelope import (
    ingest_dcx_contact_message_from_inbound_envelope,
)
from messages.store_dcx_contact_message_provider_event import (
    store_dcx_contact_message_provider_event,
)

_DCX_META_WHATSAPP_ACKNOWLEDGEMENT_TEXT = "Received. I'm analysing this now."


def process_dcx_meta_whatsapp_inbound_webhook_payload(
    webhook_payload: dict,
    store_provider_event: Callable[..., dict] | None = None,
    read_message_envelopes: Callable[[dict], list[dict]] | None = None,
    read_media_bytes: Callable[[str], dict] | None = None,
    ingest_inbound_envelope: Callable[..., dict] | None = None,
    send_whatsapp_text_message: Callable[..., dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - webhook_payload is one verified Meta WhatsApp webhook JSON object.
      postconditions:
        - Stores one provider-event row for the webhook payload.
        - Stores one canonical DCX message row per normalized inbound message envelope.
        - Downloads and stores supported media attachments when the inbound envelope references them.
        - Attempts one acknowledgement message per inbound envelope.
      side_effects:
        - writes to stephen_dcx_contact_message_provider_events
        - writes to stephen_dcx_contact_messages
        - may send outbound WhatsApp acknowledgement messages
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
        - The acknowledgement send can fail after the inbound message is already stored.
      WHAT COMES NEXT:
        - Media download, transcription, and richer trade classification can build on these stored rows.

    TESTS:
      - none yet in this first provider-intake pass

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
    except Exception as exc:
        raise RuntimeError("API_DCX_META_WHATSAPP_INBOUND_PROCESS_FAILED") from exc

    processed_messages: list[dict] = []
    acknowledged_image_source_handles: set[str] = set()
    for message_envelope in message_envelopes:
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

        acknowledgement_status = "not_sent"
        normalized_source_handle = str(message_envelope.get("source_handle") or "").strip()
        should_send_acknowledgement = message_envelope.get("should_send_ack") is True
        if (
            should_send_acknowledgement
            and message_envelope.get("message_format") == "image"
            and normalized_source_handle in acknowledged_image_source_handles
        ):
            should_send_acknowledgement = False
            acknowledgement_status = "suppressed"

        if should_send_acknowledgement:
            try:
                (send_whatsapp_text_message or send_dcx_whatsapp_text_message)(
                    phone_e164=ingest_result.get("normalized_source_handle") or normalized_source_handle,
                    message_text=_DCX_META_WHATSAPP_ACKNOWLEDGEMENT_TEXT,
                )
                acknowledgement_status = "accepted"
                if message_envelope.get("message_format") == "image" and normalized_source_handle != "":
                    acknowledged_image_source_handles.add(normalized_source_handle)
            except Exception:
                acknowledgement_status = "failed"

        processed_messages.append(
            {
                **ingest_result,
                "provider_message_id": message_envelope["provider_message_id"],
                "acknowledgement_status": acknowledgement_status,
            }
        )

    return {
        "status": "processed",
        "provider_event_id": provider_event_result["provider_event_id"],
        "processed_message_count": len(processed_messages),
        "messages": processed_messages,
    }
