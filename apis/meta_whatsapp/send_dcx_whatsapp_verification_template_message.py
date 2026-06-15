"""
CONTEXT:
This file sends one WhatsApp verification-link template message through the Meta WhatsApp Cloud API.
It exists so the DCX phone-link flow can deliver one secure verification button without leaking
provider-specific payload details into account or auth capabilities.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import httpx


def send_dcx_whatsapp_verification_template_message(
    phone_e164: str,
    template_body_greeting_name: str,
    template_body_verification_target: str,
    template_button_url_suffix: str,
    send_payload_with_provider: Callable[[str, dict, dict], Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - phone_e164 is one normalized E.164 phone number string beginning with `+`.
        - template_body_greeting_name is the value for body parameter `{{1}}`.
        - template_body_verification_target is the value for body parameter `{{2}}`.
        - template_button_url_suffix is the value for URL button parameter `{{1}}`.
        - META_WHATSAPP_TOKEN is configured in the backend environment.
        - META_PHONE_NUMBER_ID is configured in the backend environment.
        - META_WHATSAPP_VERIFY_TEMPLATE_NAME is configured in the backend environment.
        - META_WHATSAPP_VERIFY_TEMPLATE_LANGUAGE_CODE is configured in the backend environment.
        - META_API_VERSION is configured in the backend environment.
      postconditions:
        - Sends one WhatsApp template message carrying the verification link to the target phone.
        - Returns one provider delivery summary with provider message id when available.
      side_effects:
        - sends one WhatsApp message through the configured Meta business account
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The first production WhatsApp identity step should use one provider adapter instead of scattering Meta payload shape and environment handling across account capabilities.
      WHEN TO USE it:
        - Use it after one WhatsApp link challenge has been prepared and persisted successfully.
      WHEN NOT TO USE it:
        - Do not use it for browser-facing responses.
        - Do not use it for inbound webhook handling or free-text replies.
      WHAT CAN GO WRONG:
        - Meta configuration can be missing.
        - The template can be unpublished, misnamed, or rejected by the provider.
        - Provider network or auth errors can reject the send.
      WHAT COMES NEXT:
        - Later WhatsApp flows can add richer template variants or non-template senders behind the same adapter folder without changing the account-phone capabilities.

    TESTS:
      - meta_whatsapp_verify_adapter_builds_expected_template_payload
      - meta_whatsapp_verify_adapter_raises_clear_error_when_required_config_missing
      - meta_whatsapp_verify_adapter_raises_clear_error_when_provider_send_fails

    ERRORS:
      - API_DCX_WHATSAPP_VERIFY_PROVIDER_CONFIGURATION_MISSING:
          suggested_action: Configure the required Meta WhatsApp environment values before sending verification links.
          common_causes:
            - missing META_WHATSAPP_TOKEN
            - missing META_PHONE_NUMBER_ID
            - missing META_WHATSAPP_VERIFY_TEMPLATE_NAME
            - missing META_WHATSAPP_VERIFY_TEMPLATE_LANGUAGE_CODE
            - missing META_API_VERSION
          recovery_steps:
            - Add the missing Meta configuration values.
            - Restart the backend.
            - Retry the request.
          retry_safe: true
      - API_DCX_WHATSAPP_VERIFY_PROVIDER_SEND_FAILED:
          suggested_action: Confirm the Meta template configuration and retry after the provider is healthy.
          common_causes:
            - invalid or expired Meta token
            - unpublished template
            - provider outage
          recovery_steps:
            - Verify the business account token and template name.
            - Retry after Meta is healthy.
          retry_safe: false
          what_changed:
            - unknown whether Meta accepted, rejected, or partially processed the outbound request
          rollback_needed: false
          rollback_operation:
            - none in the provider adapter; the owning account-phone flow decides whether to resend or invalidate state

    CODE:
    """
    meta_whatsapp_token = os.getenv("META_WHATSAPP_TOKEN", "").strip()
    meta_phone_number_id = os.getenv("META_PHONE_NUMBER_ID", "").strip()
    meta_whatsapp_verify_template_name = os.getenv("META_WHATSAPP_VERIFY_TEMPLATE_NAME", "").strip()
    meta_whatsapp_verify_template_language_code = os.getenv(
        "META_WHATSAPP_VERIFY_TEMPLATE_LANGUAGE_CODE", ""
    ).strip()
    meta_api_version = os.getenv("META_API_VERSION", "").strip()

    missing_config_vars: list[str] = []
    if meta_whatsapp_token == "":
        missing_config_vars.append("META_WHATSAPP_TOKEN")
    if meta_phone_number_id == "":
        missing_config_vars.append("META_PHONE_NUMBER_ID")
    if meta_whatsapp_verify_template_name == "":
        missing_config_vars.append("META_WHATSAPP_VERIFY_TEMPLATE_NAME")
    if meta_whatsapp_verify_template_language_code == "":
        missing_config_vars.append("META_WHATSAPP_VERIFY_TEMPLATE_LANGUAGE_CODE")
    if meta_api_version == "":
        missing_config_vars.append("META_API_VERSION")

    if len(missing_config_vars) > 0:
        raise RuntimeError(
            "API_DCX_WHATSAPP_VERIFY_PROVIDER_CONFIGURATION_MISSING:" + ",".join(missing_config_vars)
        )

    if not isinstance(phone_e164, str) or phone_e164.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_VERIFY_PROVIDER_SEND_FAILED")

    if not isinstance(template_body_greeting_name, str) or template_body_greeting_name.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_VERIFY_PROVIDER_SEND_FAILED")

    if (
        not isinstance(template_body_verification_target, str)
        or template_body_verification_target.strip() == ""
    ):
        raise RuntimeError("API_DCX_WHATSAPP_VERIFY_PROVIDER_SEND_FAILED")

    if not isinstance(template_button_url_suffix, str) or template_button_url_suffix.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_VERIFY_PROVIDER_SEND_FAILED")

    request_url = f"https://graph.facebook.com/{meta_api_version}/{meta_phone_number_id}/messages"
    request_headers = {
        "Authorization": f"Bearer {meta_whatsapp_token}",
        "Content-Type": "application/json",
    }
    request_payload = {
        "messaging_product": "whatsapp",
        "to": phone_e164,
        "type": "template",
        "template": {
            "name": meta_whatsapp_verify_template_name,
            "language": {
                "code": meta_whatsapp_verify_template_language_code,
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": template_body_greeting_name,
                        },
                        {
                            "type": "text",
                            "text": template_body_verification_target,
                        },
                    ],
                },
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [
                        {
                            "type": "text",
                            "text": template_button_url_suffix,
                        }
                    ],
                },
            ],
        },
    }

    try:
        send_payload = send_payload_with_provider or _send_meta_whatsapp_payload
        response = send_payload(request_url, request_headers, request_payload)
    except Exception as exc:
        raise RuntimeError("API_DCX_WHATSAPP_VERIFY_PROVIDER_SEND_FAILED") from exc

    provider_message_id = None
    if isinstance(response, dict):
        messages = response.get("messages")
        if isinstance(messages, list) and len(messages) > 0 and isinstance(messages[0], dict):
            provider_message_id = messages[0].get("id")

    return {
        "provider": "meta_whatsapp",
        "status": "accepted",
        "provider_message_id": provider_message_id,
        "provider_sender_id": meta_phone_number_id,
        "template_name": meta_whatsapp_verify_template_name,
        "template_language_code": meta_whatsapp_verify_template_language_code,
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
