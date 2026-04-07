"""
CONTEXT:
This file validates the placeholder contract for one editable live DCX email template.
It exists so internal admin editing can prevent malformed or incomplete placeholder usage
from being saved into `stephen_dcx_emails` and then shipped into real transactional sends.
"""

from __future__ import annotations

from emails.render_email_template_with_allowed_placeholders import (
    EMAIL_TEMPLATE_PLACEHOLDER_PATTERN,
)

ALLOWED_AND_REQUIRED_PLACEHOLDERS_BY_EMAIL_TEMPLATE = {
    ("transactional", "signup_verify_otp"): {
        "allowed": {"otp_code", "verify_otp_url"},
        "required": {"otp_code", "verify_otp_url"},
    },
    ("transactional", "signup_thanks_welcome"): {
        "allowed": set(),
        "required": set(),
    },
}


def validate_live_email_template_placeholder_contract_capability(
    email_type: str,
    email_key: str,
    email_subject: str,
    email_body: str,
) -> None:
    """
    CONTRACT:
      preconditions:
        - email_type and email_key identify one managed DCX email template purpose.
        - email_subject and email_body contain the candidate edited template values.
      postconditions:
        - Raises no error when the placeholder syntax and required-placeholder contract are valid.
        - Raises one stable runtime error when placeholder syntax, allowed placeholders, or required placeholders are invalid.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Internal editing is only useful if stored templates remain render-safe for the transactional flows that depend on them.
      WHEN TO USE it:
        - Use it immediately before saving an edited live email row version.
      WHEN NOT TO USE it:
        - Do not use it for arbitrary user-authored prose outside the managed email-template system.
      WHAT CAN GO WRONG:
        - A required placeholder can be removed.
        - An unsupported placeholder can be introduced.
        - Partial `{{ ... }}` syntax can be left behind by mistake.
      WHAT COMES NEXT:
        - Save the new immutable live version only after this contract is satisfied.

    TESTS:
      - allows_valid_signup_verify_otp_placeholders
      - rejects_missing_required_placeholder
      - rejects_unapproved_placeholder
      - rejects_partial_placeholder_syntax

    ERRORS:
      - API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_NOT_ALLOWED:
          suggested_action: Remove the unsupported placeholder or explicitly add support for it in code.
          common_causes:
            - typo in placeholder code
            - unsupported new placeholder introduced through admin editing
          recovery_steps:
            - Correct the placeholder code in the email template.
            - Or extend the allowed placeholder contract in code first.
          retry_safe: true
      - API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_REQUIRED_MISSING:
          suggested_action: Reinsert the required placeholder before saving this template.
          common_causes:
            - required placeholder removed during editing
            - translated template forgot the required code
          recovery_steps:
            - Add the exact required placeholder token back into the template.
          retry_safe: true
      - API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_SYNTAX_INVALID:
          suggested_action: Correct the malformed placeholder braces before saving.
          common_causes:
            - partial `{{` or `}}` left in the subject or body
            - placeholder edited into a non-matching shape
          recovery_steps:
            - Replace malformed placeholder text with one exact supported token or plain text.
          retry_safe: true

    CODE:
    """
    placeholder_rules = ALLOWED_AND_REQUIRED_PLACEHOLDERS_BY_EMAIL_TEMPLATE.get(
        (email_type, email_key),
        {
            "allowed": set(),
            "required": set(),
        },
    )
    allowed_placeholder_codes = placeholder_rules["allowed"]
    required_placeholder_codes = placeholder_rules["required"]

    combined_template_text = f"{email_subject}\n{email_body}"
    discovered_placeholder_codes = set(
        EMAIL_TEMPLATE_PLACEHOLDER_PATTERN.findall(combined_template_text)
    )

    unexpected_placeholder_codes = sorted(
        placeholder_code
        for placeholder_code in discovered_placeholder_codes
        if placeholder_code not in allowed_placeholder_codes
    )
    if unexpected_placeholder_codes:
        raise RuntimeError(
            "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_NOT_ALLOWED:"
            + ",".join(unexpected_placeholder_codes)
        )

    missing_required_placeholder_codes = sorted(
        placeholder_code
        for placeholder_code in required_placeholder_codes
        if placeholder_code not in discovered_placeholder_codes
    )
    if missing_required_placeholder_codes:
        raise RuntimeError(
            "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_REQUIRED_MISSING:"
            + ",".join(missing_required_placeholder_codes)
        )

    template_text_without_valid_placeholders = EMAIL_TEMPLATE_PLACEHOLDER_PATTERN.sub(
        "",
        combined_template_text,
    )
    if (
        "{{" in template_text_without_valid_placeholders
        or "}}" in template_text_without_valid_placeholders
    ):
        raise RuntimeError("API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_SYNTAX_INVALID")
