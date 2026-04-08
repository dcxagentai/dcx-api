"""
CONTEXT:
This file holds the shared token and URL helpers for DCX password setup/reset challenges.
It exists so signup OTP verification, forgot-password request, and password completion all
use the same opaque token contract and app-domain handoff rules.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

DCX_PASSWORD_LINK_CHALLENGE_TYPE = "password_link"
DCX_PASSWORD_SETUP_CHALLENGE_PURPOSE = "password_setup"
DCX_PASSWORD_RESET_CHALLENGE_PURPOSE = "password_reset"
DCX_PASSWORD_LINK_TOKEN_LIFETIME_MS = 60 * 60 * 1000


def build_dcx_password_link_challenge_token() -> str:
    """
    CONTRACT:
      preconditions:
        - none
      postconditions:
        - Returns one opaque random token suitable for browser/email password-link handoff.
      side_effects: []
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Password setup and reset should use opaque one-time tokens instead of exposing challenge ids.
      WHEN TO USE it:
        - Use it when creating or refreshing a password setup/reset challenge row.
      WHEN NOT TO USE it:
        - Do not use it for session ids or OTP values.
      WHAT CAN GO WRONG:
        - Missing runtime entropy would weaken the token, but Python's secrets module is appropriate here.
      WHAT COMES NEXT:
        - Store only the keyed hash in the database and hand the raw token to the browser or email link.

    TESTS:
      - token_roundtrip_hash_normalize_path

    ERRORS: []

    CODE:
    """
    return secrets.token_urlsafe(32)


def normalize_dcx_password_link_challenge_token(raw_token: str) -> str:
    """
    CONTRACT:
      preconditions:
        - raw_token is the browser or email-link token candidate.
      postconditions:
        - Returns one trimmed token string with a safe minimum length.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The completion route should reject obviously malformed password-link tokens before database work begins.
      WHEN TO USE it:
        - Use it when accepting the password-link token from the browser.
      WHEN NOT TO USE it:
        - Do not use it for email normalization or session cookies.
      WHAT CAN GO WRONG:
        - Blank or truncated tokens should be rejected.
      WHAT COMES NEXT:
        - The normalized token can be hashed and looked up against the active challenge row.

    TESTS:
      - token_roundtrip_hash_normalize_path
      - normalize_rejects_short_token

    ERRORS:
      - API_DCX_PASSWORD_LINK_TOKEN_INVALID:
          suggested_action: Use the newest password link or request another one.
          common_causes:
            - missing token
            - truncated token
          recovery_steps:
            - Reopen the newest email or restart the setup flow.
            - Retry with the full token.
          retry_safe: true

    CODE:
    """
    normalized_token = raw_token.strip() if isinstance(raw_token, str) else ""
    if len(normalized_token) < 24:
        raise RuntimeError("API_DCX_PASSWORD_LINK_TOKEN_INVALID")

    return normalized_token


def hash_dcx_password_link_challenge_token(raw_token: str) -> str:
    """
    CONTRACT:
      preconditions:
        - raw_token is one normalized opaque password challenge token.
      postconditions:
        - Returns one keyed HMAC digest suitable for database lookup.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The password challenge token should never be stored raw in the database.
      WHEN TO USE it:
        - Use it when inserting the challenge row and when resolving a completion request.
      WHEN NOT TO USE it:
        - Do not use it for session-token hashing; the session layer owns that contract.
      WHAT CAN GO WRONG:
        - Missing secret configuration would make secure hashing impossible.
      WHAT COMES NEXT:
        - Capabilities can query the active challenge row by the stored hash.

    TESTS:
      - token_roundtrip_hash_normalize_path

    ERRORS:
      - API_DCX_PASSWORD_LINK_SECRET_MISSING:
          suggested_action: Configure the password-link secret before attempting setup or reset flows.
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
        key=_read_dcx_password_link_secret_key(),
        msg=f"password-link:{raw_token}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def build_dcx_password_set_page_url(
    challenge_purpose: str,
    raw_password_link_token: str,
    language_code: str | None = None,
) -> str:
    """
    CONTRACT:
      preconditions:
        - challenge_purpose is `password_setup` or `password_reset`.
        - raw_password_link_token is the one-time token for this flow.
      postconditions:
        - Returns one app-domain password-set URL carrying the challenge purpose and language code in query state and the token in the fragment.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Public signup and email reset links should land on the same app-side password-set page.
      WHEN TO USE it:
        - Use it when returning the signup handoff URL or rendering the password-reset email.
      WHEN NOT TO USE it:
        - Do not use it for login, logout, or public marketing links.
      WHAT CAN GO WRONG:
        - A wrong app base URL would send users to the wrong host.
      WHAT COMES NEXT:
        - The app can strip the token from the fragment, validate the password, and complete the challenge through the API.

    TESTS:
      - builds_setup_and_reset_urls_against_local_default

    ERRORS:
      - API_DCX_PASSWORD_LINK_PURPOSE_INVALID:
          suggested_action: Retry through the intended setup or reset flow.
          common_causes:
            - unsupported challenge purpose
          recovery_steps:
            - Restart the password flow from the proper entry point.
          retry_safe: true

    CODE:
    """
    if challenge_purpose not in {
        DCX_PASSWORD_SETUP_CHALLENGE_PURPOSE,
        DCX_PASSWORD_RESET_CHALLENGE_PURPOSE,
    }:
        raise RuntimeError("API_DCX_PASSWORD_LINK_PURPOSE_INVALID")

    normalized_language_code = (
        language_code.strip().lower()
        if isinstance(language_code, str) and language_code.strip() != ""
        else "en"
    )

    return (
        f"{read_dcx_app_base_url().rstrip('/')}/password/set"
        f"?mode={challenge_purpose}&language_code={normalized_language_code}"
        f"#password_challenge_token={raw_password_link_token}"
    )


def read_dcx_app_base_url() -> str:
    """
    CONTRACT:
      preconditions:
        - Optional app-base-url environment variables may or may not be set.
      postconditions:
        - Returns one normalized app base URL for local or hosted password handoff links.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Password setup/reset links should always land on the app surface, not on the API or public site.
      WHEN TO USE it:
        - Use it when building password set or reset links.
      WHEN NOT TO USE it:
        - Do not use it for admin-only route generation.
      WHAT CAN GO WRONG:
        - Missing hosted configuration can leave a production link pointed at localhost.
      WHAT COMES NEXT:
        - Hosted environments can set `DCX_APP_BASE_URL` explicitly while local development uses the default app port.

    TESTS:
      - builds_setup_and_reset_urls_against_local_default

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


def _read_dcx_password_link_secret_key() -> bytes:
    """Minimal contract: return one non-empty secret key for DCX password-link HMAC operations."""
    configured_secret = os.getenv("DCX_AUTH_CHALLENGE_SECRET", "").strip()
    if configured_secret != "":
        return configured_secret.encode("utf-8")

    fallback_secret = os.getenv("DCX_EMAIL_SIGNUP_OTP_SECRET", "").strip()
    if fallback_secret != "":
        return fallback_secret.encode("utf-8")

    raise RuntimeError("API_DCX_PASSWORD_LINK_SECRET_MISSING")
