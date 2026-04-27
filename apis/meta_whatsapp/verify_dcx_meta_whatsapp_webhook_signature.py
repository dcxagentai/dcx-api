"""
CONTEXT:
This file verifies incoming DCX Meta WhatsApp webhook requests.
It exists so the public WhatsApp webhook boundary can authenticate real Meta requests before they
become stored provider events or user-visible messages.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os


def verify_dcx_meta_whatsapp_webhook_signature(
    raw_request_body: bytes,
    signature_header_value: str | None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - raw_request_body is the exact unmodified request body bytes from Meta.
        - signature_header_value is the inbound `X-Hub-Signature-256` header value.
        - META_APP_SECRET is configured in the backend environment.
      postconditions:
        - Returns the parsed webhook JSON payload when the signature is valid.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Incoming WhatsApp messages are security-sensitive and must not be trusted without provider verification.
      WHEN TO USE it:
        - Use it at the start of the public Meta WhatsApp POST webhook route.
      WHEN NOT TO USE it:
        - Do not use it for the initial GET handshake challenge.
      WHAT CAN GO WRONG:
        - The Meta app secret can be missing.
        - The signature header can be missing or tampered with.
        - The body can be malformed JSON.
      WHAT COMES NEXT:
        - Verified payloads can be normalized into canonical DCX contact messages.

    TESTS:
      - none yet in this first webhook-ingest pass

    ERRORS:
      - API_DCX_META_WHATSAPP_WEBHOOK_SECRET_MISSING:
          suggested_action: Configure META_APP_SECRET before enabling inbound WhatsApp processing.
          common_causes:
            - missing META_APP_SECRET
          recovery_steps:
            - Add META_APP_SECRET to the backend environment.
            - Restart the backend.
          retry_safe: true
      - API_DCX_META_WHATSAPP_WEBHOOK_INVALID:
          suggested_action: Retry with a genuine signed webhook request from Meta.
          common_causes:
            - missing signature header
            - signature mismatch
            - malformed JSON body
          recovery_steps:
            - Confirm the raw request body is passed unchanged into verification.
            - Confirm the Meta app secret matches the current app.
          retry_safe: true

    CODE:
    """
    meta_app_secret = os.getenv("META_APP_SECRET", "").strip()
    if meta_app_secret == "":
        raise RuntimeError("API_DCX_META_WHATSAPP_WEBHOOK_SECRET_MISSING")

    normalized_signature_header = signature_header_value.strip() if isinstance(signature_header_value, str) else ""
    if not normalized_signature_header.startswith("sha256="):
        raise RuntimeError("API_DCX_META_WHATSAPP_WEBHOOK_INVALID")

    expected_signature = "sha256=" + hmac.new(
        key=meta_app_secret.encode("utf-8"),
        msg=raw_request_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(normalized_signature_header, expected_signature):
        raise RuntimeError("API_DCX_META_WHATSAPP_WEBHOOK_INVALID")

    try:
        return json.loads(raw_request_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("API_DCX_META_WHATSAPP_WEBHOOK_INVALID") from exc
