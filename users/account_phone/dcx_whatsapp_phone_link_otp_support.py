"""
CONTEXT:
This file holds the shared constants and normalization helpers for linking one WhatsApp phone
number to an already authenticated DCX account.
It exists so request, verify, and summary capabilities can share one stable challenge purpose,
one OTP hashing rule, and one E.164 normalization policy.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets

DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE = "otp"
DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE = "account_whatsapp_phone_link"
DCX_WHATSAPP_PHONE_LINK_CHANNEL = "whatsapp"
DCX_WHATSAPP_PHONE_LINK_OTP_LIFETIME_MS = 10 * 60 * 1000
DCX_WHATSAPP_PHONE_LINK_MAX_VERIFY_ATTEMPTS = 5
DCX_WHATSAPP_PHONE_LINK_SEND_COOLDOWN_MS = 30 * 1000
DCX_WHATSAPP_PHONE_LINK_MAX_SENDS_PER_WINDOW = 3
DCX_WHATSAPP_PHONE_LINK_SEND_BUDGET_WINDOW_MS = 15 * 60 * 1000
DCX_WHATSAPP_PHONE_LINK_OTP_PATTERN = re.compile(r"^[0-9]{6}$")
DCX_WHATSAPP_PHONE_LINK_E164_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")


def normalize_dcx_whatsapp_phone_link_phone_e164(candidate_phone_number: str) -> str:
    """
    CONTRACT:
      preconditions:
        - candidate_phone_number is one user-entered phone string.
      postconditions:
        - Returns one normalized E.164 phone string suitable for persistent identity matching.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - WhatsApp identity linking should compare one canonical phone representation, not many local formatting variants.
      WHEN TO USE it:
        - Use it before persisting, comparing, or sending one WhatsApp phone verification challenge.
      WHEN NOT TO USE it:
        - Do not use it for display formatting back to the user.
      WHAT CAN GO WRONG:
        - The user can enter one local-only number without a country code.
        - The string can contain invalid characters or be too short.
      WHAT COMES NEXT:
        - The normalized phone can be used as the pending delivery target and, after verification, as the live WhatsApp identity subject.

    TESTS:
      - normalizes_phone_with_spaces_hyphens_and_00_prefix
      - raises_clear_error_for_invalid_phone_shape

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_INVALID:
          suggested_action: Re-enter the phone with country code, for example +34600000001.
          common_causes:
            - missing country code
            - invalid characters
            - too short or too long
          recovery_steps:
            - Enter the number with `+` and the country code.
            - Remove local punctuation or extension text.
          retry_safe: true

    CODE:
    """
    if not isinstance(candidate_phone_number, str):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_INVALID")

    normalized_phone_number = re.sub(r"[\s\-\(\)]", "", candidate_phone_number.strip())

    if normalized_phone_number.startswith("00"):
        normalized_phone_number = "+" + normalized_phone_number[2:]

    if not DCX_WHATSAPP_PHONE_LINK_E164_PATTERN.fullmatch(normalized_phone_number):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_INVALID")

    return normalized_phone_number


def normalize_dcx_whatsapp_phone_link_otp_code(candidate_otp_code: str) -> str:
    """
    CONTRACT:
      preconditions:
        - candidate_otp_code is one user-entered OTP candidate.
      postconditions:
        - Returns one normalized six-digit OTP string.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - OTP verification should compare one canonical digit-only code, not formatting variants.
      WHEN TO USE it:
        - Use it before verifying one WhatsApp phone-link challenge.
      WHEN NOT TO USE it:
        - Do not use it for password or session token handling.
      WHAT CAN GO WRONG:
        - The code can be incomplete or contain non-digit characters.
      WHAT COMES NEXT:
        - The normalized OTP can be hashed and compared against the pending challenge row.

    TESTS:
      - normalizes_six_digit_otp
      - raises_clear_error_for_invalid_otp_shape

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_OTP_INVALID:
          suggested_action: Enter the six-digit WhatsApp code exactly as received.
          common_causes:
            - missing digits
            - non-numeric characters
          recovery_steps:
            - Re-enter the code carefully.
            - Request a new code if the message expired.
          retry_safe: true

    CODE:
    """
    if not isinstance(candidate_otp_code, str):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_OTP_INVALID")

    normalized_otp_code = re.sub(r"\s", "", candidate_otp_code.strip())
    if not DCX_WHATSAPP_PHONE_LINK_OTP_PATTERN.fullmatch(normalized_otp_code):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_OTP_INVALID")

    return normalized_otp_code


def generate_dcx_whatsapp_phone_link_otp_code() -> str:
    """Minimal contract: return one six-digit numeric OTP string."""
    return f"{secrets.randbelow(1000000):06d}"


def generate_dcx_whatsapp_phone_link_otp_salt() -> str:
    """Minimal contract: return one random salt string suitable for OTP hashing."""
    return secrets.token_hex(16)


def hash_dcx_whatsapp_phone_link_otp_code(otp_code: str, otp_salt: str) -> str:
    """
    CONTRACT:
      preconditions:
        - otp_code is one normalized six-digit OTP.
        - otp_salt is one non-empty random salt string.
      postconditions:
        - Returns one deterministic HMAC-SHA256 hash for the OTP.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The database should never store raw WhatsApp OTP codes.
      WHEN TO USE it:
        - Use it before writing or comparing one phone-link OTP challenge.
      WHEN NOT TO USE it:
        - Do not use it for passwords or session tokens.
      WHAT CAN GO WRONG:
        - The configured OTP secret can be missing.
      WHAT COMES NEXT:
        - The resulting hash can be compared to the stored pending challenge row during verification.

    TESTS:
      - hashes_same_otp_and_salt_deterministically
      - falls_back_to_email_signup_secret_when_whatsapp_secret_missing

    ERRORS:
      - API_DCX_WHATSAPP_PHONE_OTP_SECRET_MISSING:
          suggested_action: Configure one OTP secret in the backend environment before linking phones.
          common_causes:
            - missing DCX_WHATSAPP_PHONE_OTP_SECRET
            - missing fallback DCX_EMAIL_SIGNUP_OTP_SECRET
          recovery_steps:
            - Add DCX_WHATSAPP_PHONE_OTP_SECRET to the backend environment.
            - Or keep using DCX_EMAIL_SIGNUP_OTP_SECRET as the temporary shared secret.
          retry_safe: true

    CODE:
    """
    otp_secret = (
        os.getenv("DCX_WHATSAPP_PHONE_OTP_SECRET", "").strip()
        or os.getenv("DCX_EMAIL_SIGNUP_OTP_SECRET", "").strip()
    )
    if otp_secret == "":
        raise RuntimeError("API_DCX_WHATSAPP_PHONE_OTP_SECRET_MISSING")

    return hmac.new(
        key=otp_secret.encode("utf-8"),
        msg=f"{otp_salt}:{otp_code}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
