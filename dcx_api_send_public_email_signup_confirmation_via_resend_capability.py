"""
CONTEXT:
This file sends the public DCX email-signup confirmation email through Resend.
It exists so the OTP verification route can add one post-confirmation courtesy email without
coupling the browser success path to provider-side delivery details.
"""

from __future__ import annotations

import html
import os
from typing import Any, Callable


def send_public_email_signup_confirmation_via_resend_capability(
    email_delivery_draft: dict,
    confirmed_email: str,
    send_email_via_resend: Callable[[str, dict], Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_delivery_draft contains recipient_email, subject, and text_body for one confirmed signup.
        - confirmed_email identifies the confirmed recipient email for log-safe internal correlation.
        - RESEND_API_KEY is configured in the backend environment.
      postconditions:
        - Sends one confirmation email through Resend.
        - Returns one internal delivery summary for server-side use only.
      side_effects:
        - sends one email through the configured Resend account
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: public_email_signup_confirmation_send:{confirmed_email}
      locks: []
      contention_strategy: rely on the caller to trigger this only after one successful confirmation event

    NARRATIVE:
      WHY this exists:
        - The confirmation email is a nice follow-up touch, but it should remain a best-effort provider side effect.
      WHEN TO USE it:
        - Use it after the OTP verification capability has already confirmed the user successfully.
      WHEN NOT TO USE it:
        - Do not use it for OTP delivery, resend operations, or broader lifecycle campaigns.
      WHAT CAN GO WRONG:
        - The API key or sender config can be missing.
        - The provider can reject the send.
      WHAT COMES NEXT:
        - The route can log failures and still return confirmation success to the browser.

    TESTS:
      - builds_test_mode_params_with_default_sender_and_override_recipient
      - returns_internal_delivery_summary_when_provider_accepts_send
      - raises_clear_error_when_resend_api_key_missing

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_API_KEY_MISSING:
          suggested_action: Configure RESEND_API_KEY before attempting email delivery.
          common_causes:
            - missing backend env variable
          recovery_steps:
            - Add the API key.
            - Restart the backend.
            - Retry the request only if confirmation email delivery is important.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED:
          suggested_action: Check provider configuration and retry later if needed.
          common_causes:
            - invalid sender configuration
            - provider outage
          recovery_steps:
            - Verify the sender settings.
            - Retry after the provider is healthy.
          retry_safe: false
          what_changed: the user is already confirmed even if the follow-up email failed
          rollback_needed: false
          rollback_operation: none; keep the confirmed user state and treat the email as best effort
      - API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN:
          suggested_action: Remove the test-recipient override or explicitly enable it for local testing only.
          common_causes:
            - test recipient override left configured in a non-local environment
          recovery_steps:
            - Remove DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT.
            - Or set DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE=true in a local-only environment.
          retry_safe: true

    CODE:
    """
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()

    if resend_api_key == "":
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_RESEND_API_KEY_MISSING")

    sender_name = os.getenv("DCX_EMAIL_SIGNUP_RESEND_FROM_NAME", "DCX").strip() or "DCX"
    sender_email = (
        os.getenv("DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL", "onboarding@resend.dev").strip()
        or "onboarding@resend.dev"
    )
    test_recipient_override = os.getenv("DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT", "").strip() or None
    runtime_environment = os.getenv("DCX_ENVIRONMENT", "").strip().lower()

    if test_recipient_override is not None and (
        runtime_environment not in {"local", "development"}
        or os.getenv("DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE", "").strip().lower() != "true"
    ):
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN")

    actual_recipient_email = test_recipient_override or email_delivery_draft["recipient_email"]

    resend_send_params = {
        "from": f"{sender_name} <{sender_email}>",
        "to": [actual_recipient_email],
        "subject": email_delivery_draft["subject"],
        "text": email_delivery_draft["text_body"],
        "html": _build_html_email_body_from_text(email_delivery_draft["text_body"]),
    }

    try:
        provider_response = (send_email_via_resend or _send_email_via_resend_sdk)(
            resend_api_key,
            resend_send_params,
        )
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED") from exc

    provider_message_id = None

    if isinstance(provider_response, dict):
        provider_message_id = provider_response.get("id")
    else:
        provider_message_id = getattr(provider_response, "id", None)

    return {
        "provider": "resend",
        "status": "accepted",
        "confirmed_email": confirmed_email,
        "provider_message_id": provider_message_id,
    }


def _build_html_email_body_from_text(text_body: str) -> str:
    """Minimal contract: convert the plain-text draft into a simple HTML body for Resend."""
    return "<div>" + html.escape(text_body).replace("\n", "<br />") + "</div>"


def _send_email_via_resend_sdk(resend_api_key: str, resend_send_params: dict) -> Any:
    """Minimal contract: lazily import Resend, configure the API key, and send the email."""
    import resend

    resend.api_key = resend_api_key
    return resend.Emails.send(resend_send_params)
