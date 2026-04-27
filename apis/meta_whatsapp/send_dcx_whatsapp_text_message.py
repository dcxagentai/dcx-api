"""
CONTEXT:
This file sends one free-text WhatsApp message through the Meta WhatsApp Cloud API.
It exists so inbound WhatsApp intake can acknowledge message receipt without leaking provider-specific
payload details into route or message-domain code.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import httpx


def send_dcx_whatsapp_text_message(
    phone_e164: str,
    message_text: str,
    send_payload_with_provider: Callable[[str, dict, dict], Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - phone_e164 is one normalized E.164 phone number string beginning with `+`.
        - message_text is one non-empty text body.
        - META_WHATSAPP_TOKEN, META_PHONE_NUMBER_ID, and META_API_VERSION are configured.
      postconditions:
        - Sends one free-text WhatsApp message and returns the provider message id when available.
      side_effects:
        - sends one WhatsApp message through the configured Meta business account
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - Traders should get one immediate acknowledgement that DCX received the inbound WhatsApp message.
      WHEN TO USE it:
        - Use it only as a short acknowledgement within the open inbound WhatsApp conversation window.
      WHEN NOT TO USE it:
        - Do not use it for template-only verification flows or inbound webhook verification.
      WHAT CAN GO WRONG:
        - Meta configuration can be missing.
        - The provider can reject the free-text send.
      WHAT COMES NEXT:
        - Later reply flows can send richer text or media messages through the same provider folder.

    TESTS:
      - none yet in this first webhook-ingest pass

    ERRORS:
      - API_DCX_WHATSAPP_TEXT_PROVIDER_CONFIGURATION_MISSING:
          suggested_action: Configure the required Meta WhatsApp environment values before sending acknowledgements.
          common_causes:
            - missing META_WHATSAPP_TOKEN
            - missing META_PHONE_NUMBER_ID
            - missing META_API_VERSION
          recovery_steps:
            - Add the missing Meta configuration values.
            - Restart the backend.
          retry_safe: true
      - API_DCX_WHATSAPP_TEXT_PROVIDER_SEND_FAILED:
          suggested_action: Confirm the Meta token and conversation window are valid, then retry if appropriate.
          common_causes:
            - invalid or expired token
            - provider rejection
            - conversation window not open
          recovery_steps:
            - Verify the Meta business account token.
            - Retry only if it is safe to send another acknowledgement.
          retry_safe: false
          what_changed:
            - unknown whether Meta accepted or rejected the outbound request
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
            "API_DCX_WHATSAPP_TEXT_PROVIDER_CONFIGURATION_MISSING:" + ",".join(missing_config_vars)
        )

    if not isinstance(phone_e164, str) or phone_e164.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_TEXT_PROVIDER_SEND_FAILED")
    if not isinstance(message_text, str) or message_text.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_TEXT_PROVIDER_SEND_FAILED")

    request_url = f"https://graph.facebook.com/{meta_api_version}/{meta_phone_number_id}/messages"
    request_headers = {
        "Authorization": f"Bearer {meta_whatsapp_token}",
        "Content-Type": "application/json",
    }
    request_payload = {
        "messaging_product": "whatsapp",
        "to": phone_e164,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message_text.strip(),
        },
    }

    try:
        response = (send_payload_with_provider or _send_meta_whatsapp_payload)(
            request_url,
            request_headers,
            request_payload,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_WHATSAPP_TEXT_PROVIDER_SEND_FAILED") from exc

    provider_message_id = None
    if isinstance(response, dict):
        messages = response.get("messages")
        if isinstance(messages, list) and len(messages) > 0 and isinstance(messages[0], dict):
            provider_message_id = messages[0].get("id")

    return {
        "provider": "meta_whatsapp",
        "status": "accepted",
        "provider_message_id": provider_message_id,
    }


def _send_meta_whatsapp_payload(request_url: str, request_headers: dict, request_payload: dict) -> dict:
    response = httpx.post(
        request_url,
        headers=request_headers,
        json=request_payload,
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()
