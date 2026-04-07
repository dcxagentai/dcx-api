"""
CONTEXT:
This file validates one DCX candidate password against the first MVP password policy.
It exists so signup password setup, password reset, and future password-change flows all
enforce the same simple but realistic passphrase-oriented rule set.
"""

from __future__ import annotations


def validate_dcx_candidate_password(
    candidate_password: str,
    confirmed_password: str | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - candidate_password is the user-submitted plaintext password.
        - confirmed_password may be provided when the frontend collects a repeated confirmation value.
      postconditions:
        - Returns one normalized validation payload when the password satisfies the MVP password rules.
        - Raises one stable runtime error when the password is blank, too short, too long, or does not match the confirmation value.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first password flow should prefer strong, memorable passphrases instead of brittle composition rules.
      WHEN TO USE it:
        - Use it before hashing any newly submitted password in setup or reset flows.
      WHEN NOT TO USE it:
        - Do not use it for current-password login checks or token validation.
      WHAT CAN GO WRONG:
        - Users can submit blank values, very short passwords, or mismatched confirmation inputs.
      WHAT COMES NEXT:
        - The validated normalized password can be passed into the Argon2id hash creation path.

    TESTS:
      - accepts_password_with_length_twelve_or_more
      - rejects_blank_candidate_password
      - rejects_short_candidate_password
      - rejects_confirmation_mismatch

    ERRORS:
      - API_DCX_PASSWORD_INVALID:
          suggested_action: Enter a password with at least 12 characters.
          common_causes:
            - blank password
            - password shorter than 12 characters
            - password longer than 200 characters
          recovery_steps:
            - Enter a longer passphrase.
            - Retry once the password meets the stated rules.
          retry_safe: true
      - API_DCX_PASSWORD_CONFIRMATION_MISMATCH:
          suggested_action: Re-enter the same password in both fields.
          common_causes:
            - confirmation typo
            - copied only one field
          recovery_steps:
            - Re-enter the password and confirmation carefully.
            - Retry the submission.
          retry_safe: true

    CODE:
    """
    normalized_candidate_password = (
        candidate_password if isinstance(candidate_password, str) else ""
    )
    normalized_confirmed_password = (
        confirmed_password if isinstance(confirmed_password, str) else None
    )

    if normalized_candidate_password.strip() == "":
        raise RuntimeError("API_DCX_PASSWORD_INVALID")

    if len(normalized_candidate_password) < 12 or len(normalized_candidate_password) > 200:
        raise RuntimeError("API_DCX_PASSWORD_INVALID")

    if (
        normalized_confirmed_password is not None
        and normalized_candidate_password != normalized_confirmed_password
    ):
        raise RuntimeError("API_DCX_PASSWORD_CONFIRMATION_MISMATCH")

    return {
        "normalized_candidate_password": normalized_candidate_password,
    }
