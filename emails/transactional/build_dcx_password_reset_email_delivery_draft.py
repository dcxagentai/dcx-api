"""
CONTEXT:
This file builds the DCX password-reset email delivery draft.
It exists so the forgot-password route can send one localized password-reset email using the
same managed-template system as the signup transactional emails.
"""

from __future__ import annotations

from typing import Any, Callable

from emails.read_live_email_template import read_live_email_template_capability
from emails.render_email_template_with_allowed_placeholders import (
    render_email_template_with_allowed_placeholders_capability,
)


def build_dcx_password_reset_email_delivery_draft(
    language_code: str,
    normalized_email: str,
    password_set_url: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - language_code is the best language code available for the user.
        - normalized_email is the canonical recipient email.
        - password_set_url is the app-domain URL carrying the one-time reset token.
      postconditions:
        - Returns one rendered password-reset email draft.
        - Falls back to a minimal English template when the managed template is not present yet.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Password reset email copy should live in the same managed email system as the rest of the transactional flow, but MVP setup should not break completely if the template has not been seeded yet.
      WHEN TO USE it:
        - Use it right before sending the password-reset email.
      WHEN NOT TO USE it:
        - Do not use it for signup OTP or confirmation delivery.
      WHAT CAN GO WRONG:
        - The managed template can be missing.
        - The template can carry unsupported placeholders.
      WHAT COMES NEXT:
        - The email send capability can pass the draft through the configured provider.

    TESTS:
      - builds_password_reset_draft_from_live_template
      - falls_back_to_inline_english_when_live_template_missing

    ERRORS:
      - API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_NOT_ALLOWED:
          suggested_action: Remove the unexpected placeholder or explicitly support it in this builder.
          common_causes:
            - unsupported placeholder in password-reset template
          recovery_steps:
            - Correct the template.
            - Retry after publishing the fix.
          retry_safe: true

    CODE:
    """
    try:
        live_template = read_live_email_template_capability(
            email_type="transactional",
            email_key="auth_password_reset",
            language_code=language_code,
            connect_to_database=connect_to_database,
        )
        email_subject = live_template["email_subject"]
        email_body = live_template["email_body"]
    except RuntimeError as runtime_error:
        if str(runtime_error) != "API_LIVE_EMAIL_TEMPLATE_NOT_FOUND":
            raise

        email_subject = "DCX Agentic: Reset your password"
        email_body = (
            "Use this secure link to choose a new DCX password:\n\n"
            "{{ password_set_url }}\n\n"
            "If you did not request this, you can ignore this email."
        )

    rendered_template = render_email_template_with_allowed_placeholders_capability(
        email_subject=email_subject,
        email_body=email_body,
        allowed_placeholder_codes={"password_set_url"},
        placeholder_values={
            "password_set_url": password_set_url,
        },
    )

    return {
        "provider": "resend",
        "recipient_email": normalized_email,
        "subject": rendered_template["email_subject"],
        "text_body": rendered_template["email_body"],
    }
