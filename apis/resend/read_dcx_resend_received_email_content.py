"""
CONTEXT:
This file reads one received-email content payload from Resend's receiving API.
It exists so inbound email webhooks can fetch the actual email body after webhook verification.
"""

from __future__ import annotations

import os
from typing import Any, Callable

import httpx


def read_dcx_resend_received_email_content(
    received_email_id: str,
    fetch_email_content_with_provider: Callable[[str, dict], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - received_email_id is one non-empty Resend received-email id.
        - RESEND_API_KEY is configured in the backend environment.
      postconditions:
        - Returns one normalized received-email content payload from Resend.
      side_effects:
        - performs one HTTPS GET to the Resend receiving API
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Resend webhooks do not include full email bodies, so DCX needs one small provider adapter to fetch them.
      WHEN TO USE it:
        - Use it after an `email.received` webhook has been verified.
      WHEN NOT TO USE it:
        - Do not use it for outbound send-status webhooks.
      WHAT CAN GO WRONG:
        - RESEND_API_KEY can be missing.
        - The email id can be invalid.
        - The provider API can fail.
      WHAT COMES NEXT:
        - Later inbound attachment retrieval can sit next to this call in the same provider folder.

    TESTS:
      - none yet in this first inbound-email pass

    ERRORS:
      - API_DCX_RESEND_RECEIVED_EMAIL_CONFIGURATION_MISSING:
          suggested_action: Configure RESEND_API_KEY before enabling inbound email processing.
          common_causes:
            - missing RESEND_API_KEY
          recovery_steps:
            - Add RESEND_API_KEY to the backend environment.
            - Restart the backend.
          retry_safe: true
      - API_DCX_RESEND_RECEIVED_EMAIL_READ_FAILED:
          suggested_action: Retry after confirming the received email id and provider health.
          common_causes:
            - invalid received email id
            - provider outage
          recovery_steps:
            - Confirm the webhook carried a real email id.
            - Retry once Resend is healthy.
          retry_safe: true

    CODE:
    """
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_api_key == "":
        raise RuntimeError("API_DCX_RESEND_RECEIVED_EMAIL_CONFIGURATION_MISSING")

    normalized_received_email_id = received_email_id.strip() if isinstance(received_email_id, str) else ""
    if normalized_received_email_id == "":
        raise RuntimeError("API_DCX_RESEND_RECEIVED_EMAIL_READ_FAILED")

    try:
        response_payload = (fetch_email_content_with_provider or _fetch_dcx_resend_received_email_content)(
            normalized_received_email_id,
            {
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
            },
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_RESEND_RECEIVED_EMAIL_READ_FAILED") from exc

    if isinstance(response_payload.get("data"), dict):
        return response_payload["data"]
    if isinstance(response_payload, dict):
        return response_payload

    raise RuntimeError("API_DCX_RESEND_RECEIVED_EMAIL_READ_FAILED")


def _fetch_dcx_resend_received_email_content(received_email_id: str, request_headers: dict) -> dict:
    response = httpx.get(
        f"https://api.resend.com/emails/receiving/{received_email_id}",
        headers=request_headers,
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()
