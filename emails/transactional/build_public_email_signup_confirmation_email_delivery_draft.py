"""
CONTEXT:
This file builds the public DCX signup confirmation delivery draft from the live email-template table.
It exists so post-verification confirmation email copy can be edited in the database without
hardcoding the body text in the OTP verification route.
"""

from __future__ import annotations

from typing import Any, Callable

from emails.read_live_email_template import read_live_email_template_capability
from emails.render_email_template_with_allowed_placeholders import (
    render_email_template_with_allowed_placeholders_capability,
)


def build_public_email_signup_confirmation_email_delivery_draft(
    language_code: str,
    normalized_email: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - language_code is the normalized public language code for this confirmed signup.
        - normalized_email is the canonical confirmed recipient email.
      postconditions:
        - Returns one localized confirmation email delivery draft using the live managed template.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Confirmation follow-up copy should be editable in the same managed multilingual system as the OTP email.
      WHEN TO USE it:
        - Use it immediately after successful OTP verification when the backend wants to send the best-effort confirmation email.
      WHEN NOT TO USE it:
        - Do not use it for OTP delivery, resend, newsletters, or sequences.
      WHAT CAN GO WRONG:
        - The live template can be missing.
        - Unexpected placeholders can appear in the template.
      WHAT COMES NEXT:
        - The provider-agnostic confirmation sender can project this draft through Resend.

    TESTS:
      - builds_confirmation_delivery_draft_from_live_template

    ERRORS:
      - API_LIVE_EMAIL_TEMPLATE_NOT_FOUND:
          suggested_action: Publish the live confirmation template before attempting delivery.
          common_causes:
            - missing `signup_thanks_welcome` live row
          recovery_steps:
            - Seed or publish the live template.
            - Retry the send if needed.
          retry_safe: true

    CODE:
    """
    live_template = read_live_email_template_capability(
        email_type="transactional",
        email_key="signup_thanks_welcome",
        language_code=language_code,
        connect_to_database=connect_to_database,
    )
    rendered_template = render_email_template_with_allowed_placeholders_capability(
        email_subject=live_template["email_subject"],
        email_body=live_template["email_body"],
        allowed_placeholder_codes=set(),
        placeholder_values={},
    )

    return {
        "recipient_email": normalized_email,
        "subject": rendered_template["email_subject"],
        "text_body": rendered_template["email_body"],
    }
