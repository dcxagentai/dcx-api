"""
CONTEXT:
This file renders one DCX email template using a strict allowed-placeholder set.
It exists so email draft builders can safely substitute only explicitly-approved values
such as OTP codes and verification links, instead of accepting arbitrary placeholder drift.
"""

from __future__ import annotations

import re

EMAIL_TEMPLATE_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def render_email_template_with_allowed_placeholders_capability(
    email_subject: str,
    email_body: str,
    allowed_placeholder_codes: set[str],
    placeholder_values: dict[str, str],
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_subject and email_body came from one live stored email template.
        - allowed_placeholder_codes contains the exact placeholder codes permitted for this email purpose.
        - placeholder_values contains string substitutions for the placeholders actually used.
      postconditions:
        - Returns one rendered email subject and body with all placeholders substituted.
        - Rejects unexpected or missing placeholder values.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Managed email copy is valuable only if placeholder substitution stays explicit and safe.
      WHEN TO USE it:
        - Use it immediately after loading one live template and before passing the rendered draft to a provider adapter.
      WHEN NOT TO USE it:
        - Do not use it for arbitrary user-authored text where placeholder injection is not part of the contract.
      WHAT CAN GO WRONG:
        - A template can contain an unapproved placeholder.
        - A required placeholder value can be missing or blank.
      WHAT COMES NEXT:
        - The transactional email builder can project the rendered result into the provider-specific draft shape.

    TESTS:
      - renders_repeated_allowed_placeholders_in_subject_and_body
      - rejects_unapproved_placeholder_codes
      - rejects_missing_placeholder_values

    ERRORS:
      - API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_NOT_ALLOWED:
          suggested_action: Remove the unexpected placeholder or add it deliberately to the allowed set in code.
          common_causes:
            - template edited with unsupported placeholder code
            - typo in placeholder name
          recovery_steps:
            - Correct the placeholder in the email template.
            - Or explicitly add support for it in the owning email builder.
          retry_safe: true
      - API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_VALUE_MISSING:
          suggested_action: Pass the required placeholder value before rendering the email.
          common_causes:
            - missing substitution value
            - blank placeholder value
          recovery_steps:
            - Populate the missing placeholder value.
            - Retry rendering.
          retry_safe: true

    CODE:
    """
    discovered_placeholder_codes = set(
        EMAIL_TEMPLATE_PLACEHOLDER_PATTERN.findall(f"{email_subject}\n{email_body}")
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

    missing_placeholder_codes = sorted(
        placeholder_code
        for placeholder_code in discovered_placeholder_codes
        if not isinstance(placeholder_values.get(placeholder_code), str)
        or placeholder_values[placeholder_code].strip() == ""
    )

    if missing_placeholder_codes:
        raise RuntimeError(
            "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_VALUE_MISSING:"
            + ",".join(missing_placeholder_codes)
        )

    def _render_value(template_text: str) -> str:
        return EMAIL_TEMPLATE_PLACEHOLDER_PATTERN.sub(
            lambda match: placeholder_values[match.group(1)],
            template_text,
        )

    return {
        "email_subject": _render_value(email_subject),
        "email_body": _render_value(email_body),
    }
