"""
CONTEXT:
This file sends the DCX password-reset email through the configured transactional provider.
It exists so the password-reset flow can stay provider-agnostic at the route and capability layers.
"""

from __future__ import annotations

from typing import Callable

from apis.resend.send_email import send_email_via_resend


def send_dcx_password_reset_email(
    email_delivery_draft: dict,
    send_email: Callable[[dict], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_delivery_draft contains recipient_email, subject, and text_body for one password-reset email.
      postconditions:
        - Sends one password-reset email through the configured provider adapter.
        - Returns one internal delivery summary.
      side_effects:
        - sends one email through the configured transactional email provider
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - Forgot-password should use the same provider abstraction style as the signup transactional mail.
      WHEN TO USE it:
        - Use it only after a password-reset draft has been rendered successfully.
      WHEN NOT TO USE it:
        - Do not use it for signup OTP or confirmation messages.
      WHAT CAN GO WRONG:
        - Provider configuration or delivery can fail.
      WHAT COMES NEXT:
        - The route can log delivery failures while still returning a generic browser response.

    TESTS:
      - password_reset_send_returns_delivery_summary_when_provider_accepts

    ERRORS: []

    CODE:
    """
    return (send_email or send_email_via_resend)(email_delivery_draft)
