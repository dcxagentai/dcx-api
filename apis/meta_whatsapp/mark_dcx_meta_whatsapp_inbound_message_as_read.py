"""
CONTEXT:
This file marks one inbound WhatsApp Cloud API message as read through Meta.
It exists so DCX can acknowledge receipt with the native WhatsApp read receipt instead of sending
an extra "received, analysing" text bubble into the trader conversation.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import httpx


def mark_dcx_meta_whatsapp_inbound_message_as_read(
    provider_message_id: str,
    mark_payload_with_provider: Callable[[str, dict, dict], Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - provider_message_id is one inbound Meta WhatsApp message id from the webhook payload.
        - META_WHATSAPP_TOKEN, META_PHONE_NUMBER_ID, and META_API_VERSION are configured.
      postconditions:
        - Sends one provider request asking Meta to mark the inbound message as read.
        - Returns one provider delivery summary when Meta accepts the read-receipt request.
      side_effects:
        - may update the sender-facing WhatsApp read receipt for one inbound message
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: meta_whatsapp_read_receipt:{provider_message_id}
      locks:
        - none; Meta treats repeated read-status writes for the same message as convergent state
      contention_strategy: repeated requests converge on the same read state

    NARRATIVE:
      WHY this exists:
        - The WhatsApp chat should feel like a native assistant, not a noisy logging stream. A blue-tick
          read receipt is enough to tell the trader that DCX has received the message while analysis runs.
      WHEN TO USE it:
        - Use it for inbound WhatsApp messages after webhook verification and message-id extraction.
      WHEN NOT TO USE it:
        - Do not use it for outbound DCX messages, app-originated messages, email, or verification templates.
      WHAT CAN GO WRONG:
        - Meta configuration can be missing.
        - The provider can reject the message id or token.
        - Read receipts may not display exactly as expected in every WhatsApp client or privacy context.
      WHAT COMES NEXT:
        - Richer WhatsApp UX can add typing indicators or interactive replies later while keeping read
          receipts as the quiet receipt signal.

    TESTS:
      - meta_whatsapp_read_receipt_adapter_builds_expected_payload
      - meta_whatsapp_read_receipt_adapter_raises_clear_error_when_required_config_missing
      - meta_whatsapp_read_receipt_adapter_raises_clear_error_when_provider_send_fails

    ERRORS:
      - API_DCX_WHATSAPP_READ_RECEIPT_PROVIDER_CONFIGURATION_MISSING:
          suggested_action: Configure the required Meta WhatsApp environment values before marking messages read.
          common_causes:
            - missing META_WHATSAPP_TOKEN
            - missing META_PHONE_NUMBER_ID
            - missing META_API_VERSION
          recovery_steps:
            - Add the missing Meta configuration values.
            - Restart the backend.
            - Retry the webhook processing if appropriate.
          retry_safe: true
      - API_DCX_WHATSAPP_READ_RECEIPT_PROVIDER_SEND_FAILED:
          suggested_action: Confirm the Meta token and inbound message id are valid, then retry if appropriate.
          common_causes:
            - blank provider_message_id
            - invalid or expired token
            - provider rejection
          recovery_steps:
            - Verify the webhook payload contains the inbound message id.
            - Check Meta provider logs.
            - Retry once the provider is healthy.
          retry_safe: true
          what_changed:
            - unknown whether Meta accepted or rejected the read-receipt request
          rollback_needed: false
          rollback_operation:
            - none

    CODE:
    """
    meta_whatsapp_token = os.getenv("META_WHATSAPP_TOKEN", "").strip()
    meta_phone_number_id = os.getenv("META_PHONE_NUMBER_ID", "").strip()
    meta_api_version = os.getenv("META_API_VERSION", "").strip()

    missing_config_vars: list[str] = []
    if meta_whatsapp_token == "":
        missing_config_vars.append("META_WHATSAPP_TOKEN")
    if meta_phone_number_id == "":
        missing_config_vars.append("META_PHONE_NUMBER_ID")
    if meta_api_version == "":
        missing_config_vars.append("META_API_VERSION")
    if missing_config_vars:
        raise RuntimeError(
            "API_DCX_WHATSAPP_READ_RECEIPT_PROVIDER_CONFIGURATION_MISSING:"
            + ",".join(missing_config_vars)
        )

    if not isinstance(provider_message_id, str) or provider_message_id.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_READ_RECEIPT_PROVIDER_SEND_FAILED")

    request_url = f"https://graph.facebook.com/{meta_api_version}/{meta_phone_number_id}/messages"
    request_headers = {
        "Authorization": f"Bearer {meta_whatsapp_token}",
        "Content-Type": "application/json",
    }
    request_payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": provider_message_id.strip(),
    }

    try:
        response = (mark_payload_with_provider or _send_meta_whatsapp_payload)(
            request_url,
            request_headers,
            request_payload,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_WHATSAPP_READ_RECEIPT_PROVIDER_SEND_FAILED") from exc

    return {
        "provider": "meta_whatsapp",
        "status": "accepted",
        "provider_response_json": response if isinstance(response, dict) else {},
    }


def _send_meta_whatsapp_payload(request_url: str, request_headers: dict, request_payload: dict) -> dict:
    """Minimal contract: POST one JSON payload to Meta and return the decoded response body."""
    response = httpx.post(
        request_url,
        headers=request_headers,
        json=request_payload,
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()
