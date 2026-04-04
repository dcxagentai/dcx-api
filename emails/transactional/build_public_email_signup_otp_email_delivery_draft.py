"""
CONTEXT:
This file builds the public DCX signup OTP delivery draft from the live email-template table.
It exists so signup and resend can send localized OTP emails with strict placeholder rendering
without hardcoding subject/body copy in the signup flow helpers.
"""

from __future__ import annotations

from typing import Any, Callable

from emails.read_live_email_template import read_live_email_template_capability
from emails.render_email_template_with_allowed_placeholders import (
    render_email_template_with_allowed_placeholders_capability,
)


def build_public_email_signup_otp_email_delivery_draft(
    language_code: str,
    normalized_email: str,
    otp_code: str,
    verification_link_url: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - language_code is the normalized public language code for this send.
        - normalized_email is the canonical recipient email.
        - otp_code is the raw generated OTP.
        - verification_link_url is the localized secure verification link for this challenge.
      postconditions:
        - Returns one localized OTP email delivery draft with rendered placeholders.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - OTP email content now lives in the managed `stephen_dcx_emails` table and should be rendered
          with only the placeholder values this flow explicitly allows.
      WHEN TO USE it:
        - Use it right before sending the signup or resend OTP email.
      WHEN NOT TO USE it:
        - Do not use it for confirmation, newsletter, or sequence email.
      WHAT CAN GO WRONG:
        - The live template can be missing.
        - The template can contain an unsupported placeholder.
      WHAT COMES NEXT:
        - The provider-agnostic send capability can deliver the rendered draft.

    TESTS:
      - builds_otp_delivery_draft_from_live_template_with_rendered_placeholders

    ERRORS:
      - API_LIVE_EMAIL_TEMPLATE_NOT_FOUND:
          suggested_action: Publish the live OTP template before attempting delivery.
          common_causes:
            - missing `signup_verify_otp` live row
          recovery_steps:
            - Seed or publish the live template.
            - Retry the send.
          retry_safe: true
      - API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_NOT_ALLOWED:
          suggested_action: Remove the unexpected placeholder or explicitly support it in this builder.
          common_causes:
            - unsupported placeholder in template copy
          recovery_steps:
            - Correct the template.
            - Retry after publishing the fixed template.
          retry_safe: true
      - API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_VALUE_MISSING:
          suggested_action: Provide the required OTP or verify-link value before rendering.
          common_causes:
            - missing OTP code
            - missing verification link
          recovery_steps:
            - Restore the required values.
            - Retry rendering.
          retry_safe: true

    CODE:
    """
    live_template = read_live_email_template_capability(
        email_type="transactional",
        email_key="signup_verify_otp",
        language_code=language_code,
        connect_to_database=connect_to_database,
    )
    rendered_template = render_email_template_with_allowed_placeholders_capability(
        email_subject=live_template["email_subject"],
        email_body=live_template["email_body"],
        allowed_placeholder_codes={"otp_code", "verify_otp_url"},
        placeholder_values={
            "otp_code": otp_code,
            "verify_otp_url": verification_link_url,
        },
    )

    return {
        "provider": "resend",
        "recipient_email": normalized_email,
        "subject": rendered_template["email_subject"],
        "text_body": rendered_template["email_body"],
        "verification_link_url": verification_link_url,
    }
