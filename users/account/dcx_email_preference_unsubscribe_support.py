"""
CONTEXT:
This file holds the signed-token and URL helpers for DCX public email-preference unsubscribe links.
It exists so newsletter and future promotional emails can carry one-click unsubscribe links without
requiring an active browser session or a stored challenge row.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Callable
from urllib.parse import quote

DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_ALL = "all"
DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_PROMOTIONAL = "promotional"
DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_NEWSLETTERS = "newsletters"
DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_LIFETIME_MS = 180 * 24 * 60 * 60 * 1000
_ALLOWED_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_KINDS = {
    DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_ALL,
    DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_PROMOTIONAL,
    DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_NEWSLETTERS,
}


def build_dcx_email_preference_unsubscribe_token(
    user_id: int,
    recipient_email: str,
    unsubscribe_kind: str,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> str:
    """
    CONTRACT:
      preconditions:
        - user_id is one positive DCX user id.
        - recipient_email is one non-empty normalized email value for the outbound recipient.
        - unsubscribe_kind is one supported unsubscribe kind.
      postconditions:
        - Returns one signed opaque token suitable for public email unsubscribe links.
      side_effects: []
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Outbound email unsubscribe links should be stateless and safe to verify later without storing raw tokens.
      WHEN TO USE it:
        - Use it while building one-click unsubscribe URLs for newsletter or promotional email footers.
      WHEN NOT TO USE it:
        - Do not use it for sessions, password links, or signup OTP flows.
      WHAT CAN GO WRONG:
        - Missing secret configuration would make secure token signing impossible.
        - Unsupported unsubscribe kinds should be rejected before the link is emitted.
      WHAT COMES NEXT:
        - The public unsubscribe route can verify the token and apply the requested preference change.

    TESTS:
      - builds_and_reads_unsubscribe_token_roundtrip
      - rejects_expired_unsubscribe_token

    ERRORS:
      - API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_KIND_INVALID:
          suggested_action: Retry with one supported unsubscribe link kind.
          common_causes:
            - unsupported kind value
          recovery_steps:
            - Rebuild the unsubscribe links with one supported kind.
          retry_safe: true
      - API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_INVALID:
          suggested_action: Rebuild the unsubscribe link with a valid recipient and user id.
          common_causes:
            - blank recipient email
            - invalid user id
          recovery_steps:
            - Retry with one valid recipient snapshot.
          retry_safe: true

    CODE:
    """
    normalized_unsubscribe_kind = _normalize_dcx_email_preference_unsubscribe_kind(
        unsubscribe_kind
    )
    normalized_recipient_email = (
        recipient_email.strip().lower()
        if isinstance(recipient_email, str)
        else ""
    )
    if not isinstance(user_id, int) or user_id <= 0 or normalized_recipient_email == "":
        raise RuntimeError("API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_INVALID")

    current_timestamp_ms = (
        current_timestamp_ms_provider() if current_timestamp_ms_provider else _read_current_timestamp_ms()
    )
    payload = {
        "uid": user_id,
        "em": normalized_recipient_email,
        "kind": normalized_unsubscribe_kind,
        "exp": current_timestamp_ms + DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_LIFETIME_MS,
    }
    payload_segment = _encode_dcx_email_preference_unsubscribe_payload(payload)
    signature_segment = _sign_dcx_email_preference_unsubscribe_payload_segment(
        payload_segment
    )
    return f"{payload_segment}.{signature_segment}"


def read_dcx_email_preference_unsubscribe_token_payload(
    raw_token: str,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - raw_token is one public email unsubscribe token candidate.
      postconditions:
        - Returns one verified token payload with user id, recipient email, unsubscribe kind, and expiry.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The unsubscribe route needs one stable way to verify and decode stateless unsubscribe links.
      WHEN TO USE it:
        - Use it while resolving a public one-click unsubscribe request.
      WHEN NOT TO USE it:
        - Do not use it for arbitrary query strings or non-DCX signed links.
      WHAT CAN GO WRONG:
        - Tokens can be blank, malformed, expired, or tampered with.
      WHAT COMES NEXT:
        - The verified payload can drive the preference update and any needed suppression changes.

    TESTS:
      - builds_and_reads_unsubscribe_token_roundtrip
      - rejects_expired_unsubscribe_token

    ERRORS:
      - API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_INVALID:
          suggested_action: Use the newest unsubscribe link from the email and retry.
          common_causes:
            - malformed token
            - signature mismatch
            - missing payload fields
          recovery_steps:
            - Reopen the original email.
            - Retry from the full unsubscribe URL.
          retry_safe: true
      - API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_EXPIRED:
          suggested_action: Use a newer email or change preferences from the signed-in account page.
          common_causes:
            - old email link
          recovery_steps:
            - Reopen the most recent email.
            - Or update preferences from the account page.
          retry_safe: true

    CODE:
    """
    normalized_token = raw_token.strip() if isinstance(raw_token, str) else ""
    token_parts = normalized_token.split(".")
    if len(token_parts) != 2 or token_parts[0] == "" or token_parts[1] == "":
        raise RuntimeError("API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_INVALID")

    expected_signature_segment = _sign_dcx_email_preference_unsubscribe_payload_segment(
        token_parts[0]
    )
    if not hmac.compare_digest(token_parts[1], expected_signature_segment):
        raise RuntimeError("API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_INVALID")

    payload = _decode_dcx_email_preference_unsubscribe_payload(token_parts[0])
    current_timestamp_ms = (
        current_timestamp_ms_provider() if current_timestamp_ms_provider else _read_current_timestamp_ms()
    )
    if payload["exp"] < current_timestamp_ms:
        raise RuntimeError("API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_EXPIRED")

    return payload


def build_dcx_email_preference_unsubscribe_url(
    unsubscribe_kind: str,
    raw_token: str,
) -> str:
    """
    CONTRACT:
      preconditions:
        - unsubscribe_kind is one supported unsubscribe kind.
        - raw_token is one signed unsubscribe token.
      postconditions:
        - Returns one absolute public API URL for the unsubscribe action.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Email bodies need one consistent absolute URL shape for one-click unsubscribe links.
      WHEN TO USE it:
        - Use it while rendering outbound newsletter or promotional email footers.
      WHEN NOT TO USE it:
        - Do not use it for app-internal navigation.
      WHAT CAN GO WRONG:
        - Missing hosted API configuration can point production emails at localhost if no explicit base URL is set.
      WHAT COMES NEXT:
        - Public routes can apply the unsubscribe and show a human-readable confirmation page.

    TESTS:
      - builds_unsubscribe_url_against_configured_api_base_url

    ERRORS:
      - API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_KIND_INVALID:
          suggested_action: Retry with one supported unsubscribe kind.
          common_causes:
            - unsupported kind value
          recovery_steps:
            - Rebuild the unsubscribe links with one supported kind.
          retry_safe: true

    CODE:
    """
    normalized_unsubscribe_kind = _normalize_dcx_email_preference_unsubscribe_kind(
        unsubscribe_kind
    )
    configured_api_base_url = os.getenv("DCX_API_BASE_URL", "").strip().rstrip("/")
    if configured_api_base_url == "":
        runtime_environment = os.getenv("DCX_ENVIRONMENT", "local").strip().lower() or "local"
        configured_api_base_url = (
            "https://api.dcxagent.ai"
            if runtime_environment in {"production", "staging"}
            else "http://localhost:8000"
        )

    return (
        f"{configured_api_base_url}/public/email-preferences/unsubscribe/"
        f"{quote(normalized_unsubscribe_kind)}/{quote(raw_token)}"
    )


def _normalize_dcx_email_preference_unsubscribe_kind(unsubscribe_kind: str) -> str:
    normalized_unsubscribe_kind = (
        unsubscribe_kind.strip().lower()
        if isinstance(unsubscribe_kind, str)
        else ""
    )
    if normalized_unsubscribe_kind not in _ALLOWED_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_KINDS:
        raise RuntimeError("API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_KIND_INVALID")
    return normalized_unsubscribe_kind


def _encode_dcx_email_preference_unsubscribe_payload(payload: dict) -> str:
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")


def _decode_dcx_email_preference_unsubscribe_payload(payload_segment: str) -> dict:
    try:
        padded_payload_segment = payload_segment + "=" * (-len(payload_segment) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded_payload_segment.encode("utf-8"))
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive parsing
        raise RuntimeError("API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_INVALID") from exc

    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("uid"), int)
        or payload["uid"] <= 0
        or not isinstance(payload.get("em"), str)
        or payload["em"].strip() == ""
        or not isinstance(payload.get("kind"), str)
        or not isinstance(payload.get("exp"), int)
    ):
        raise RuntimeError("API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_INVALID")

    return {
        "user_id": payload["uid"],
        "recipient_email": payload["em"].strip().lower(),
        "unsubscribe_kind": _normalize_dcx_email_preference_unsubscribe_kind(payload["kind"]),
        "exp": payload["exp"],
    }


def _sign_dcx_email_preference_unsubscribe_payload_segment(payload_segment: str) -> str:
    return hmac.new(
        key=_read_dcx_email_preference_unsubscribe_secret_key(),
        msg=f"email-preference-unsubscribe:{payload_segment}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _read_dcx_email_preference_unsubscribe_secret_key() -> bytes:
    configured_secret = os.getenv("DCX_AUTH_CHALLENGE_SECRET", "").strip()
    if configured_secret != "":
        return configured_secret.encode("utf-8")

    fallback_secret = os.getenv("DCX_SIGNUP_OTP_SECRET", "").strip()
    if fallback_secret != "":
        return fallback_secret.encode("utf-8")

    raise RuntimeError("API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_INVALID")


def _read_current_timestamp_ms() -> int:
    return int(time.time() * 1000)
