"""
CONTEXT:
This file sends the public DCX email-signup OTP email.
It exists so the signup flow can ask for one transactional OTP delivery without exposing the
current provider choice in the domain-level filename or route layer.
"""

from __future__ import annotations

from typing import Callable

from apis.resend.send_email import send_email_via_resend


def send_public_email_signup_otp(
    email_delivery_draft: dict,
    challenge_id: int,
    send_email: Callable[[dict], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_delivery_draft contains recipient_email, subject, and text_body.
        - challenge_id identifies the active signup challenge the email belongs to.
      postconditions:
        - Sends one OTP email through the configured transactional email adapter.
        - Returns one internal delivery summary for server-side use only.
      side_effects:
        - sends one email through the configured transactional email provider
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The route layer should trigger OTP delivery by business purpose, not by provider name.
      WHEN TO USE it:
        - Use it only after the signup or resend capability decides a fresh send is required.
      WHEN NOT TO USE it:
        - Do not use it for confirmation or marketing email.
      WHAT CAN GO WRONG:
        - Provider configuration or upstream delivery can fail.
      WHAT COMES NEXT:
        - The browser still receives only the minimal flow token while the backend keeps delivery details internal.

    TESTS:
      - signup_otp_send_returns_internal_delivery_summary_when_provider_accepts_send

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:
          suggested_action: Configure the transactional email provider before attempting OTP delivery.
          common_causes:
            - missing provider credentials
            - missing sender identity values
          recovery_steps:
            - Add the required provider configuration.
            - Restart the backend.
            - Retry the request.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_DRAFT_INVALID:
          suggested_action: Rebuild the OTP email draft before attempting delivery.
          common_causes:
            - missing recipient_email
            - missing subject
            - missing text_body
          recovery_steps:
            - Inspect the OTP draft builder output.
            - Restore the missing draft fields.
            - Retry the send once the draft is complete.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED:
          suggested_action: Check provider configuration and retry later.
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
        "challenge_id": challenge_id,
    }
