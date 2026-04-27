"""
CONTEXT:
This file holds the shared constants, normalization helpers, secure token helpers, and
app-link builders for linking one WhatsApp phone number to a DCX account.
It exists so send, verify, and account-summary capabilities can share one stable challenge
purpose, one phone normalization policy, and one browser-safe fragment-token handoff shape.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets

DCX_WHATSAPP_PHONE_LINK_CHALLENGE_TYPE = "whatsapp_link"
DCX_WHATSAPP_PHONE_LINK_CHALLENGE_PURPOSE = "account_whatsapp_phone_link"
DCX_WHATSAPP_PHONE_LINK_CHANNEL = "whatsapp"
DCX_WHATSAPP_PHONE_LINK_TOKEN_LIFETIME_MS = 10 * 60 * 1000
DCX_WHATSAPP_PHONE_LINK_SEND_COOLDOWN_MS = 30 * 1000
DCX_WHATSAPP_PHONE_LINK_MAX_SENDS_PER_WINDOW = 3
DCX_WHATSAPP_PHONE_LINK_SEND_BUDGET_WINDOW_MS = 15 * 60 * 1000
DCX_WHATSAPP_PHONE_LINK_E164_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")
DCX_WHATSAPP_PHONE_LINK_TOKEN_HASH_PREFIX = "#whatsapp_phone_link_token="


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


def build_dcx_whatsapp_phone_link_challenge_token() -> str:
    """
    CONTRACT:
      preconditions:
        - none
      postconditions:
        - Returns one opaque random token suitable for browser and WhatsApp button-link handoff.
      side_effects: []
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Phone verification should use opaque one-time tokens instead of exposing challenge ids or raw database keys.
      WHEN TO USE it:
        - Use it when creating or refreshing one WhatsApp phone-link challenge row.
      WHEN NOT TO USE it:
        - Do not use it for session ids or OTP values.
      WHAT CAN GO WRONG:
        - Missing runtime entropy would weaken the token, but Python's secrets module is appropriate here.
      WHAT COMES NEXT:
        - Store only the keyed hash in the database and send the raw token through the WhatsApp template link.

    TESTS:
      - token_roundtrip_hash_normalize_path

    ERRORS: []

    CODE:
    """
    return secrets.token_urlsafe(32)


def normalize_dcx_whatsapp_phone_link_challenge_token(raw_token: str) -> str:
    """
    CONTRACT:
      preconditions:
        - raw_token is the browser or WhatsApp-link token candidate.
      postconditions:
        - Returns one trimmed token string with a safe minimum length.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The verification route should reject obviously malformed phone-link tokens before database work begins.
      WHEN TO USE it:
        - Use it when accepting the phone-link token from the app browser route.
      WHEN NOT TO USE it:
        - Do not use it for phone-number normalization or session cookies.
      WHAT CAN GO WRONG:
        - Blank or truncated tokens should be rejected.
      WHAT COMES NEXT:
        - The normalized token can be hashed and looked up against the active challenge row.

    TESTS:
      - token_roundtrip_hash_normalize_path
      - normalize_rejects_short_token

    ERRORS:
      - API_DCX_WHATSAPP_PHONE_LINK_TOKEN_INVALID:
          suggested_action: Use the newest WhatsApp verification link or request another one from the account page.
          common_causes:
            - missing token
            - truncated token
          recovery_steps:
            - Reopen the newest WhatsApp message.
            - Request another verification link if needed.
          retry_safe: true

    CODE:
    """
    normalized_token = raw_token.strip() if isinstance(raw_token, str) else ""
    if len(normalized_token) < 24:
        raise RuntimeError("API_DCX_WHATSAPP_PHONE_LINK_TOKEN_INVALID")

    return normalized_token


def hash_dcx_whatsapp_phone_link_challenge_token(raw_token: str) -> str:
    """
    CONTRACT:
      preconditions:
        - raw_token is one normalized opaque WhatsApp phone-link token.
      postconditions:
        - Returns one keyed HMAC digest suitable for database lookup.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The phone-link token should never be stored raw in the database.
      WHEN TO USE it:
        - Use it when inserting the challenge row and when resolving a verification-click request.
      WHEN NOT TO USE it:
        - Do not use it for session-token hashing; the session layer owns that contract.
      WHAT CAN GO WRONG:
        - Missing secret configuration would make secure hashing impossible.
      WHAT COMES NEXT:
        - Capabilities can query the active challenge row by the stored hash.

    TESTS:
      - token_roundtrip_hash_normalize_path

    ERRORS:
      - API_DCX_WHATSAPP_PHONE_LINK_SECRET_MISSING:
          suggested_action: Configure the WhatsApp phone-link secret before attempting this verification flow.
          common_causes:
            - missing auth challenge secret
            - missing signup OTP secret fallback
          recovery_steps:
            - Add the required environment variable.
            - Restart the backend.
          retry_safe: true

    CODE:
    """
    return hmac.new(
        key=_read_dcx_whatsapp_phone_link_secret_key(),
        msg=f"whatsapp-phone-link:{raw_token}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def build_dcx_whatsapp_phone_link_verification_page_suffix(
    raw_phone_link_token: str,
    language_code: str | None = None,
) -> str:
    """
    CONTRACT:
      preconditions:
        - raw_phone_link_token is the one-time token for this flow.
      postconditions:
        - Returns one app-path suffix carrying the language code in the path and the token in the fragment.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The approved WhatsApp template already owns the app-domain prefix, so this helper should emit only the language-safe suffix we append at send time.
      WHEN TO USE it:
        - Use it when preparing the outbound WhatsApp template payload.
      WHEN NOT TO USE it:
        - Do not use it for server-side redirects or email links.
      WHAT CAN GO WRONG:
        - A wrong language code would land on the wrong localized app route.
      WHAT COMES NEXT:
        - The app route can capture the fragment token and complete the verification through the API.

    TESTS:
      - builds_localized_fragment_suffix

    ERRORS: []

    CODE:
    """
    normalized_language_code = (
        language_code.strip().lower()
        if isinstance(language_code, str) and language_code.strip() != ""
        else "en"
    )
    return (
        f"{normalized_language_code}/t/verify-whatsapp-phone"
        f"{DCX_WHATSAPP_PHONE_LINK_TOKEN_HASH_PREFIX}{raw_phone_link_token}"
    )


def build_dcx_whatsapp_phone_link_verification_page_url(
    raw_phone_link_token: str,
    language_code: str | None = None,
) -> str:
    """
    CONTRACT:
      preconditions:
        - raw_phone_link_token is the one-time token for this flow.
      postconditions:
        - Returns one full app-domain verification URL.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Local manual testing and operational reporting both benefit from one full derived verification URL in addition to the template suffix.
      WHEN TO USE it:
        - Use it for local manual simulation, logs, and test assertions.
      WHEN NOT TO USE it:
        - Do not send the full URL into the Meta URL button parameter because the template already owns the base domain.
      WHAT CAN GO WRONG:
        - A wrong app base URL would send users to the wrong host.
      WHAT COMES NEXT:
        - The browser can open the app route and complete the verification through the API.

    TESTS:
      - builds_full_verification_url_against_local_default

    ERRORS: []

    CODE:
    """
    return (
        f"{read_dcx_app_base_url().rstrip('/')}/"
        f"{build_dcx_whatsapp_phone_link_verification_page_suffix(raw_phone_link_token, language_code)}"
    )


def read_dcx_app_base_url() -> str:
    """
    CONTRACT:
      preconditions:
        - Optional app-base-url environment variables may or may not be set.
      postconditions:
        - Returns one normalized app base URL for local or hosted WhatsApp-link handoff links.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - WhatsApp verification links should always land on the app surface, not on the API or public site.
      WHEN TO USE it:
        - Use it when building full verification URLs for testing or operational reporting.
      WHEN NOT TO USE it:
        - Do not use it for admin-only route generation.
      WHAT CAN GO WRONG:
        - Missing hosted configuration can leave a production link pointed at localhost.
      WHAT COMES NEXT:
        - Hosted environments can set `DCX_APP_BASE_URL` explicitly while local development uses the default app port.

    TESTS:
      - builds_full_verification_url_against_local_default

    ERRORS: []

    CODE:
    """
    configured_app_base_url = os.getenv("DCX_APP_BASE_URL", "").strip()
    if configured_app_base_url != "":
        return configured_app_base_url

    runtime_environment = os.getenv("DCX_ENVIRONMENT", "local").strip().lower() or "local"
    if runtime_environment in {"production", "staging"}:
        return "https://app.dcxagent.ai"

    return "http://localhost:5173"


def _read_dcx_whatsapp_phone_link_secret_key() -> bytes:
    """Minimal contract: return one non-empty secret key for DCX WhatsApp phone-link HMAC operations."""
    configured_secret = os.getenv("DCX_AUTH_CHALLENGE_SECRET", "").strip()
    if configured_secret != "":
        return configured_secret.encode("utf-8")

    fallback_secret = os.getenv("DCX_SIGNUP_OTP_SECRET", "").strip()
    if fallback_secret != "":
        return fallback_secret.encode("utf-8")

    raise RuntimeError("API_DCX_WHATSAPP_PHONE_LINK_SECRET_MISSING")
