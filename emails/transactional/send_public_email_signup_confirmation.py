"""
CONTEXT:
This file sends the public DCX email-signup confirmation email.
It exists so OTP verification can trigger one post-confirmation courtesy email without embedding
the current provider name in the route or domain filename.
"""

from __future__ import annotations

from typing import Callable

from apis.resend.send_email import send_email_via_resend


def send_public_email_signup_confirmation(
    email_delivery_draft: dict,
    confirmed_email: str,
    send_email: Callable[[dict], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_delivery_draft contains recipient_email, subject, and text_body for one confirmed signup.
        - confirmed_email identifies the confirmed recipient email for log-safe internal correlation.
      postconditions:
        - Sends one confirmation email through the configured transactional email adapter.
        - Returns one internal delivery summary for server-side use only.
      side_effects:
        - sends one email through the configured transactional email provider
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The confirmation email is a business-level follow-up action and should not carry provider naming in its main module surface.
      WHEN TO USE it:
        - Use it after OTP verification has already confirmed the user successfully.
      WHEN NOT TO USE it:
        - Do not use it for OTP delivery, resend operations, or marketing campaigns.
      WHAT CAN GO WRONG:
        - Provider configuration or upstream delivery can fail.
      WHAT COMES NEXT:
        - The route can log best-effort delivery failure while still returning success to the browser.

    TESTS:
      - signup_confirmation_send_returns_internal_delivery_summary_when_provider_accepts_send

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:
          suggested_action: Configure the transactional email provider before attempting confirmation delivery.
          common_causes:
            - missing provider credentials
            - missing sender identity values
          recovery_steps:
            - Add the required provider configuration.
            - Restart the backend.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_DRAFT_INVALID:
          suggested_action: Rebuild the confirmation email draft before attempting delivery.
          common_causes:
            - missing recipient_email
            - missing subject
            - missing text_body
          recovery_steps:
            - Inspect the confirmation draft builder output.
            - Restore the missing draft fields.
            - Retry the send once the draft is complete.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED:
          suggested_action: Check provider configuration and retry later if needed.
          common_causes:
            - provider outage
            - invalid sender configuration
          recovery_steps:
            - Verify provider settings.
            - Retry after the provider is healthy.
          retry_safe: false

    CODE:
    """
    delivery_summary = (send_email or send_email_via_resend)(email_delivery_draft)
    return {
        **delivery_summary,
        "confirmed_email": confirmed_email,
    }
