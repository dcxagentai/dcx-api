"""
CONTEXT:
This file verifies one incoming DCX Resend webhook request using Resend's Svix-compatible headers.
It exists so provider webhooks are authenticated before they mutate recipient delivery state or
email suppressions inside the DCX backend.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Callable, Mapping


def verify_dcx_resend_webhook_request(
    raw_request_body: str,
    request_headers: Mapping[str, str],
    current_timestamp_seconds_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - raw_request_body is the exact raw webhook request body string.
        - request_headers contains the incoming webhook signature headers.
        - RESEND_WEBHOOK_SECRET is configured in the backend environment.
      postconditions:
        - Returns the parsed webhook payload when the signature and timestamp are valid.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Provider webhooks are security-sensitive and must be verified before the backend trusts their payloads.
      WHEN TO USE it:
        - Use it at the start of the Resend webhook route before any payload handling.
      WHEN NOT TO USE it:
        - Do not use it for browser requests or internal admin routes.
      WHAT CAN GO WRONG:
        - The webhook secret can be missing.
        - The raw body can be changed before verification.
        - Headers can be missing, malformed, expired, or tampered with.
      WHAT COMES NEXT:
        - Verified payloads can be applied to recipient delivery rows and suppression state.

    TESTS:
      - verifies_valid_resend_webhook_request
      - rejects_resend_webhook_request_with_invalid_signature

    ERRORS:
      - API_DCX_RESEND_WEBHOOK_SECRET_MISSING:
          suggested_action: Configure the Resend webhook secret before enabling webhook processing.
          common_causes:
            - missing RESEND_WEBHOOK_SECRET
          recovery_steps:
            - Add the webhook secret from the Resend dashboard.
            - Restart the backend.
          retry_safe: true
      - API_DCX_RESEND_WEBHOOK_INVALID:
          suggested_action: Retry with the original signed webhook request from Resend.
          common_causes:
            - missing headers
            - signature mismatch
            - malformed JSON body
          recovery_steps:
            - Confirm the raw body is used for verification.
            - Confirm the secret and headers match the webhook endpoint.
          retry_safe: true
      - API_DCX_RESEND_WEBHOOK_EXPIRED:
          suggested_action: Ensure the server clock is correct and rely on the next webhook retry.
          common_causes:
            - replayed webhook
            - clock skew
          recovery_steps:
            - Verify server time sync.
            - Wait for the next legitimate retry from Resend.
          retry_safe: true

    CODE:
    """
    webhook_secret = os.getenv("RESEND_WEBHOOK_SECRET", "").strip()
    if webhook_secret == "":
        raise RuntimeError("API_DCX_RESEND_WEBHOOK_SECRET_MISSING")

    lower_headers = {key.lower(): value for key, value in request_headers.items()}
    webhook_id = lower_headers.get("svix-id") or lower_headers.get("webhook-id") or ""
    webhook_timestamp = lower_headers.get("svix-timestamp") or lower_headers.get("webhook-timestamp") or ""
    webhook_signature = lower_headers.get("svix-signature") or lower_headers.get("webhook-signature") or ""
    if webhook_id == "" or webhook_timestamp == "" or webhook_signature == "":
        raise RuntimeError("API_DCX_RESEND_WEBHOOK_INVALID")

    try:
        webhook_timestamp_seconds = int(webhook_timestamp)
    except ValueError as exc:
        raise RuntimeError("API_DCX_RESEND_WEBHOOK_INVALID") from exc

    current_timestamp_seconds = (
        current_timestamp_seconds_provider()
        if current_timestamp_seconds_provider
        else int(time.time())
    )
    if abs(current_timestamp_seconds - webhook_timestamp_seconds) > 300:
        raise RuntimeError("API_DCX_RESEND_WEBHOOK_EXPIRED")

    signed_content = f"{webhook_id}.{webhook_timestamp}.{raw_request_body}"
    signing_secret = webhook_secret.removeprefix("whsec_").encode("utf-8")
    expected_signature = base64.b64encode(
        hmac.new(
            key=signing_secret,
            msg=signed_content.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    supplied_signatures = [
        signature_part.split(",", 1)[1]
        for signature_part in webhook_signature.split()
        if signature_part.startswith("v1,") and "," in signature_part
    ]
    if not any(
        hmac.compare_digest(candidate_signature, expected_signature)
        for candidate_signature in supplied_signatures
    ):
        raise RuntimeError("API_DCX_RESEND_WEBHOOK_INVALID")

    try:
        return json.loads(raw_request_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("API_DCX_RESEND_WEBHOOK_INVALID") from exc
