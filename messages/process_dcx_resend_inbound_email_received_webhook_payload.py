"""
CONTEXT:
This file processes one verified Resend `email.received` webhook payload into one canonical DCX
contact-message row.
It exists so inbound emails sent to DCX addresses become stored, derived messages in the same
pipeline as app and WhatsApp intake.
"""

from __future__ import annotations

from email.utils import getaddresses, parseaddr
from typing import Any, Callable

from apis.resend.read_dcx_resend_received_email_content import (
    read_dcx_resend_received_email_content,
)
from apis.resend.read_dcx_resend_received_email_attachment_inputs import (
    read_dcx_resend_received_email_attachment_fetch_result,
    read_dcx_resend_received_email_attachment_inputs,
)
from messages.ingest_dcx_contact_message_from_inbound_envelope import (
    ingest_dcx_contact_message_from_inbound_envelope,
)
from messages.store_dcx_contact_message_provider_event import (
    store_dcx_contact_message_provider_event,
)


def process_dcx_resend_inbound_email_received_webhook_payload(
    webhook_payload: dict,
    store_provider_event: Callable[..., dict] | None = None,
    read_received_email_content: Callable[[str], dict] | None = None,
    read_received_email_attachment_inputs: Callable[[str], list[dict] | dict] | None = None,
    ingest_inbound_envelope: Callable[..., dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - webhook_payload is one verified Resend webhook payload.
        - webhook_payload.type is `email.received`.
      postconditions:
        - Stores one provider-event row for the webhook payload.
        - Fetches the full email content from Resend.
        - Fetches supported attachment bytes when present.
        - Stores one canonical DCX inbound email message row and runs the first derivation pass.
      side_effects:
        - writes to stephen_dcx_contact_message_provider_events
        - writes to stephen_dcx_contact_messages
        - may write to stephen_dcx_contact_message_processing_jobs
        - may write to stephen_dcx_contact_message_analysis_runs
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: resend_received_email:{email_id}
      locks:
        - delegated to provider-event and message-ingest capabilities
      contention_strategy: duplicate received-email webhooks converge through provider-message id deduplication

    NARRATIVE:
      WHY this exists:
        - Traders should be able to send structured or messy emails into DCX and have them appear in the same Messages inbox.
      WHEN TO USE it:
        - Use it only after the Resend webhook request has already been verified and the event type is `email.received`.
      WHEN NOT TO USE it:
        - Do not use it for outbound delivery-status events.
      WHAT CAN GO WRONG:
        - The received email id can be missing.
        - The Resend receiving API can fail.
        - The sender may not map to a known DCX user contact method.
      WHAT COMES NEXT:
        - Later inbound attachment retrieval and document analysis can extend this same email intake path.

    TESTS:
      - none yet in this first provider-intake pass

    ERRORS:
      - API_DCX_RESEND_INBOUND_EMAIL_EVENT_INVALID:
          suggested_action: Retry with a verified `email.received` webhook payload from Resend.
          common_causes:
            - wrong event type
            - missing email id
          recovery_steps:
            - Confirm the event type is `email.received`.
            - Confirm the payload includes `data.email_id`.
          retry_safe: true
      - API_DCX_RESEND_INBOUND_EMAIL_PROCESS_FAILED:
          suggested_action: Retry after confirming the webhook payload and provider API are healthy.
          common_causes:
            - receiving API failure
            - database failure
          recovery_steps:
            - Confirm RESEND_API_KEY and webhook verification.
            - Retry once the backend and provider are healthy.
          retry_safe: true

    CODE:
    """
    event_type = (webhook_payload.get("type") or "").strip()
    event_data = webhook_payload.get("data") if isinstance(webhook_payload.get("data"), dict) else {}
    received_email_id = (event_data.get("email_id") or "").strip()
    if event_type != "email.received" or received_email_id == "":
        raise RuntimeError("API_DCX_RESEND_INBOUND_EMAIL_EVENT_INVALID")

    try:
        store_event = store_provider_event or store_dcx_contact_message_provider_event
        provider_event_result = store_event(
            provider_type="resend_inbound",
            channel_type="email",
            provider_event_type="email.received",
            provider_event_id=received_email_id,
            provider_message_id=received_email_id,
            provider_sender_handle=_read_dcx_normalized_email_address(event_data.get("from")),
            provider_recipient_handle=_read_first_dcx_recipient_email_address(event_data.get("to")),
            raw_event_payload_json=webhook_payload,
            signature_verified=True,
            processing_status="processed",
        )
        received_email_content = (read_received_email_content or read_dcx_resend_received_email_content)(
            received_email_id
        )
        received_email_attachment_fetch_result = (
            read_received_email_attachment_inputs or read_dcx_resend_received_email_attachment_fetch_result
        )(received_email_id)
        if isinstance(received_email_attachment_fetch_result, dict):
            received_email_attachment_inputs = [
                attachment_input
                for attachment_input in received_email_attachment_fetch_result.get("attachment_inputs", [])
                if isinstance(attachment_input, dict)
            ]
            skipped_attachment_reads = [
                skipped_attachment_read
                for skipped_attachment_read in received_email_attachment_fetch_result.get("skipped_attachment_reads", [])
                if isinstance(skipped_attachment_read, dict)
            ]
        else:
            received_email_attachment_inputs = [
                attachment_input
                for attachment_input in (received_email_attachment_fetch_result or [])
                if isinstance(attachment_input, dict)
            ]
            skipped_attachment_reads = []
        ingest_result = (ingest_inbound_envelope or ingest_dcx_contact_message_from_inbound_envelope)(
            provider_event_row_id=provider_event_result["provider_event_id"],
            provider_type="resend_inbound",
            channel_type="email",
            provider_message_id=received_email_id,
            source_handle=_read_dcx_normalized_email_address(
                received_email_content.get("from") or event_data.get("from")
            )
            or "",
            target_handle=_read_first_dcx_recipient_email_address(
                received_email_content.get("to") or event_data.get("to")
            ),
            message_format="text",
            raw_text_content=_read_dcx_inbound_email_body_text(received_email_content),
            received_at_ts_ms=_read_dcx_resend_received_email_timestamp_ms(
                received_email_content.get("created_at") or event_data.get("created_at")
            ),
            message_subject=(received_email_content.get("subject") or event_data.get("subject") or "").strip(),
            message_metadata_json={
                "resend_received_email_id": received_email_id,
                "resend_from": received_email_content.get("from") or event_data.get("from"),
                "resend_to": received_email_content.get("to") or event_data.get("to"),
                "resend_headers": received_email_content.get("headers") if isinstance(received_email_content.get("headers"), dict) else {},
                "resend_html_present": bool(received_email_content.get("html")),
                "resend_skipped_attachment_reads": skipped_attachment_reads,
            },
            attachment_inputs=received_email_attachment_inputs,
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_RESEND_INBOUND_EMAIL_PROCESS_FAILED") from exc

    return {
        "status": "processed",
        "provider_event_id": provider_event_result["provider_event_id"],
        "message_id": ingest_result["message_id"],
        "job_id": ingest_result["job_id"],
        "processing_status": ingest_result["processing_status"],
        "derivation_status": ingest_result["derivation_status"],
        "resolved_user_id": ingest_result["resolved_user_id"],
        "resolution_status": ingest_result["resolution_status"],
    }


def _read_dcx_normalized_email_address(raw_email_value: Any) -> str | None:
    if isinstance(raw_email_value, str):
        parsed_address = parseaddr(raw_email_value)[1].strip().lower()
        return parsed_address or None
    return None


def _read_first_dcx_recipient_email_address(raw_to_value: Any) -> str | None:
    if isinstance(raw_to_value, str):
        parsed_addresses = [address for _, address in getaddresses([raw_to_value]) if address]
        return parsed_addresses[0].strip().lower() if parsed_addresses else None
    if isinstance(raw_to_value, list):
        parsed_addresses = [address for _, address in getaddresses(raw_to_value) if address]
        return parsed_addresses[0].strip().lower() if parsed_addresses else None
    return None


def _read_dcx_inbound_email_body_text(received_email_content: dict) -> str:
    text_body = received_email_content.get("text")
    if isinstance(text_body, str) and text_body.strip() != "":
        return text_body.strip()

    html_body = received_email_content.get("html")
    if isinstance(html_body, str) and html_body.strip() != "":
        return html_body.strip()

    return ""


def _read_dcx_resend_received_email_timestamp_ms(raw_timestamp: Any) -> int:
    from datetime import datetime

    if isinstance(raw_timestamp, str) and raw_timestamp.strip() != "":
        normalized_timestamp = raw_timestamp.replace("Z", "+00:00")
        return int(datetime.fromisoformat(normalized_timestamp).timestamp() * 1000)
    return 0
