"""
CONTEXT:
This file holds the shared security helpers for the DCX public email-signup OTP flow.
It exists so the signup, verify, resend, route-boundary, and delivery capabilities all
enforce the same rules for OTP generation, flow-token handoff, URL normalization, and
origin/path validation without drifting into slightly different security behavior.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from base64 import urlsafe_b64encode
from urllib.parse import urlparse

PUBLIC_EMAIL_SIGNUP_CHALLENGE_TYPE = "email_otp"
PUBLIC_EMAIL_SIGNUP_CHALLENGE_PURPOSE = "email_signup"
PUBLIC_EMAIL_SIGNUP_OTP_LIFETIME_MS = 10 * 60 * 1000
PUBLIC_EMAIL_SIGNUP_FLOW_TOKEN_LIFETIME_MS = 30 * 60 * 1000
PUBLIC_EMAIL_SIGNUP_SEND_COOLDOWN_MS = 60 * 1000
PUBLIC_EMAIL_SIGNUP_SEND_BUDGET_WINDOW_MS = 24 * 60 * 60 * 1000
PUBLIC_EMAIL_SIGNUP_MAX_SENDS_PER_WINDOW = 6
PUBLIC_EMAIL_SIGNUP_MAX_VERIFY_ATTEMPTS = 5
PUBLIC_EMAIL_SIGNUP_LOCKOUT_MS = 15 * 60 * 1000

PUBLIC_EMAIL_SIGNUP_ALLOWED_SIGNUP_PATHS = {
    "/",
    "/landing-page-1",
    "/es/",
    "/es/pagina-1",
}
PUBLIC_EMAIL_SIGNUP_ALLOWED_VERIFY_PATHS = {
    "/users/signup-email/verify-otp",
    "/es/users/signup-email/verificar-codigo",
}
PUBLIC_EMAIL_SIGNUP_ALLOWED_CONFIRMATION_PATHS = {
    "/users/signup-email/confirmed",
    "/es/users/signup-email/confirmado",
}


def normalize_public_email_signup_origin_header(origin_header: str | None) -> str:
    """
    CONTRACT:
      preconditions:
        - origin_header is the browser-supplied Origin header for one public POST request.
      postconditions:
        - Returns one normalized allowed origin string.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The public signup flow should only accept POSTs from the exact public frontend origins we control.
      WHEN TO USE it:
        - Use it at the HTTP boundary before accepting signup, verify, or resend requests.
      WHEN NOT TO USE it:
        - Do not use it for internal server-to-server calls that do not carry browser Origin headers.
      WHAT CAN GO WRONG:
        - Missing or unknown origins should be rejected.
      WHAT COMES NEXT:
        - Route modules can cross-check the Origin header against the submitted page URL.

    TESTS:
      - normalizes_allowed_local_origin
      - rejects_missing_origin
      - rejects_unknown_origin

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_ORIGIN_INVALID:
          suggested_action: Retry the flow from the official DCX public site.
          common_causes:
            - missing Origin header
            - request sent from an unknown frontend host
          recovery_steps:
            - Reopen the official DCX public page.
            - Retry the request from that page.
          retry_safe: true

    CODE:
    """
    normalized_origin = origin_header.strip() if isinstance(origin_header, str) else ""

    if normalized_origin == "":
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_ORIGIN_INVALID")

    if normalized_origin not in _read_allowed_public_email_signup_origins():
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_ORIGIN_INVALID")

    return normalized_origin


def normalize_public_email_signup_page_url(
    page_url: str,
    expected_origin: str,
    allowed_paths: set[str],
    invalid_error_code: str,
) -> str:
    """
    CONTRACT:
      preconditions:
        - page_url is the browser runtime URL for the current public page.
        - expected_origin is the already validated browser Origin header.
        - allowed_paths contains the exact route paths accepted for this request type.
      postconditions:
        - Returns one normalized absolute URL using only the allowed origin and path.
        - Query strings and fragments are removed.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The browser can tell us which page initiated the request, but only if we normalize it and reject arbitrary query-string state.
      WHEN TO USE it:
        - Use it when accepting the landing-page signup URL, OTP verify URL, and resend URL.
      WHEN NOT TO USE it:
        - Do not use it for arbitrary external links or admin routes.
      WHAT CAN GO WRONG:
        - Relative URLs, unexpected origins, and unknown paths should all be rejected.
      WHAT COMES NEXT:
        - Persist or log only the normalized origin-plus-path form.

    TESTS:
      - strips_query_string_and_fragment
      - rejects_origin_mismatch
      - rejects_unknown_path

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_PAGE_URL_INVALID:
          suggested_action: Retry the request from the intended DCX public page.
          common_causes:
            - relative URL submitted
            - query-string polluted state
            - wrong route path
            - Origin header mismatch
          recovery_steps:
            - Reload the public page.
            - Retry the request from that page.
          retry_safe: true

    CODE:
    """
    normalized_url = page_url.strip() if isinstance(page_url, str) else ""
    parsed_url = urlparse(normalized_url)

    if parsed_url.scheme not in {"http", "https"} or parsed_url.netloc == "":
        raise RuntimeError(invalid_error_code)

    parsed_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
    normalized_path = _normalize_route_path(parsed_url.path)

    if parsed_origin != expected_origin:
        raise RuntimeError(invalid_error_code)

    if normalized_path not in allowed_paths:
        raise RuntimeError(invalid_error_code)

    return f"{parsed_origin}{normalized_path}"


def normalize_public_email_signup_email(email: str, missing_error_code: str, invalid_error_code: str) -> str:
    """
    CONTRACT:
      preconditions:
        - email is one public email-signup input value.
      postconditions:
        - Returns a trimmed lowercased canonical email.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    normalized_email = email.strip().lower() if isinstance(email, str) else ""

    if normalized_email == "":
        raise RuntimeError(missing_error_code)

    if "@" not in normalized_email:
        raise RuntimeError(invalid_error_code)

    local_part, domain_part = normalized_email.rsplit("@", 1)

    if local_part == "" or domain_part == "" or "." not in domain_part or " " in normalized_email:
        raise RuntimeError(invalid_error_code)

    return normalized_email


def normalize_public_email_signup_language_code(language_code: str, invalid_error_code: str) -> str:
    """
    CONTRACT:
      preconditions:
        - language_code is a locale-like string from the public page.
      postconditions:
        - Returns a trimmed lowercased alphabetic code.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    normalized_language_code = language_code.strip().lower() if isinstance(language_code, str) else ""

    if not normalized_language_code.isalpha() or not 2 <= len(normalized_language_code) <= 8:
        raise RuntimeError(invalid_error_code)

    return normalized_language_code


def normalize_public_email_signup_otp_code(otp_code: str, invalid_error_code: str) -> str:
    """
    CONTRACT:
      preconditions:
        - otp_code is the browser-submitted OTP string.
      postconditions:
        - Returns one six-digit OTP code.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    normalized_otp_code = otp_code.strip() if isinstance(otp_code, str) else ""

    if len(normalized_otp_code) != 6 or not normalized_otp_code.isdigit():
        raise RuntimeError(invalid_error_code)

    return normalized_otp_code


def normalize_public_email_signup_flow_token(flow_token: str, invalid_error_code: str) -> str:
    """
    CONTRACT:
      preconditions:
        - flow_token is the opaque token returned by the signup or resend route.
      postconditions:
        - Returns one trimmed token string with a minimum length.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    normalized_flow_token = flow_token.strip() if isinstance(flow_token, str) else ""

    if len(normalized_flow_token) < 24:
        raise RuntimeError(invalid_error_code)

    return normalized_flow_token


def generate_public_email_signup_otp_code() -> str:
    """
    CONTRACT:
      preconditions:
        - none
      postconditions:
        - Returns one cryptographically generated six-digit OTP string.
      side_effects: []
      idempotent: false
      retry_safe: true
      async: false

    CODE:
    """
    return f"{secrets.randbelow(900000) + 100000:06d}"


def generate_public_email_signup_otp_salt() -> str:
    """
    CONTRACT:
      preconditions:
        - none
      postconditions:
        - Returns one per-challenge random salt as a hex string.
      side_effects: []
      idempotent: false
      retry_safe: true
      async: false

    CODE:
    """
    return secrets.token_hex(16)


def build_public_email_signup_flow_token(
    challenge_id: int,
    flow_token_expires_at_ts_ms: int,
) -> str:
    """
    CONTRACT:
      preconditions:
        - challenge_id identifies the active challenge row.
        - flow_token_expires_at_ts_ms is the stored challenge token expiry timestamp.
      postconditions:
        - Returns one deterministic opaque flow token for the active challenge and expiry.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    secret_key = _read_public_email_signup_secret_key()
    payload = f"{challenge_id}:{flow_token_expires_at_ts_ms}".encode("utf-8")
    signature = hmac.new(secret_key, payload, hashlib.sha256).digest()
    encoded_payload = urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
    encoded_signature = urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"dcx1.{encoded_payload}.{encoded_signature}"


def hash_public_email_signup_otp_code(otp_code: str, otp_salt: str) -> str:
    """
    CONTRACT:
      preconditions:
        - otp_code is the raw six-digit OTP.
        - otp_salt is the per-challenge random salt.
      postconditions:
        - Returns one keyed HMAC digest suitable for database storage.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    secret_key = _read_public_email_signup_secret_key()
    return hmac.new(
        key=secret_key,
        msg=f"otp:{otp_salt}:{otp_code}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def hash_public_email_signup_flow_token(flow_token: str) -> str:
    """
    CONTRACT:
      preconditions:
        - flow_token is the raw opaque browser token.
      postconditions:
        - Returns one keyed HMAC digest for database lookup and storage.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    secret_key = _read_public_email_signup_secret_key()
    return hmac.new(
        key=secret_key,
        msg=f"flow:{flow_token}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def otp_code_matches_public_email_signup_hash(otp_code: str, otp_salt: str, expected_hash: str) -> bool:
    """
    CONTRACT:
      preconditions:
        - otp_code is one browser-submitted six-digit OTP.
        - otp_salt and expected_hash came from the stored active challenge row.
      postconditions:
        - Returns true only when the keyed HMAC hash matches the stored digest.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    candidate_hash = hash_public_email_signup_otp_code(
        otp_code=otp_code,
        otp_salt=otp_salt,
    )
    return hmac.compare_digest(candidate_hash, expected_hash)


def build_public_email_signup_otp_email_draft(language_code: str, normalized_email: str, otp_code: str) -> dict:
    """
    CONTRACT:
      preconditions:
        - language_code is the normalized locale code for this send.
        - normalized_email is the canonical recipient email.
        - otp_code is the raw generated OTP.
      postconditions:
        - Returns one localized plain-text/email payload for the send capability.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The delivery layer still needs one localized draft, but it should not leak raw browser context or extra PII.
      WHEN TO USE it:
        - Use it right before the Resend send capability.
      WHEN NOT TO USE it:
        - Do not use it for marketing broadcasts or confirmed-user newsletters.
      WHAT CAN GO WRONG:
        - Locale drift can produce the fallback English copy.
      WHAT COMES NEXT:
        - Later we can swap this hard-coded copy for managed templates without changing the route contract.

    TESTS:
      - english_draft_contains_only_essential_otp_copy
      - spanish_draft_contains_only_essential_otp_copy

    ERRORS: []

    CODE:
    """
    if language_code == "es":
        subject = "Tu código de acceso de DCX"
        text_body = (
            "Hola,\n\n"
            f"Tu código de acceso de DCX es: {otp_code}\n\n"
            "Caduca en 10 minutos.\n"
            "Si no solicitaste este código, puedes ignorar este correo."
        )
    else:
        subject = "Your DCX access code"
        text_body = (
            "Hello,\n\n"
            f"Your DCX access code is: {otp_code}\n\n"
            "It expires in 10 minutes.\n"
            "If you did not request this code, you can ignore this email."
        )

    return {
        "provider": "resend",
        "recipient_email": normalized_email,
        "subject": subject,
        "text_body": text_body,
    }


def build_public_email_signup_verification_link_url(
    public_origin: str,
    language_code: str,
    signup_flow_token: str,
) -> str:
    """
    CONTRACT:
      preconditions:
        - public_origin is one allowed public frontend origin.
        - language_code is the normalized language code for the current challenge.
        - signup_flow_token is the opaque resume token for the active challenge.
      postconditions:
        - Returns one localized verification-page link containing the opaque signup flow token in the URL fragment.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The signup flow must be resumable across devices, crashes, tab closures, and later return visits.
      WHEN TO USE it:
        - Use it when building the OTP email draft for signup and resend.
      WHEN NOT TO USE it:
        - Do not use it for public marketing links or authenticated app links.
      WHAT CAN GO WRONG:
        - If the origin is wrong, the link will resume on the wrong frontend.
      WHAT COMES NEXT:
        - The public OTP page can read the token from the fragment, store it in session storage, strip it from the URL, and continue verification safely.

    TESTS:
      - builds_english_verification_link_with_signup_flow_token
      - builds_spanish_verification_link_with_signup_flow_token

    ERRORS: []

    CODE:
    """
    verification_path = _verification_path_for_public_email_signup_language(language_code)
    return f"{public_origin}{verification_path}#signup_flow_token={signup_flow_token}"


def build_public_email_signup_otp_email_delivery_draft(
    language_code: str,
    normalized_email: str,
    otp_code: str,
    verification_link_url: str,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - language_code is the normalized locale code for this send.
        - normalized_email is the canonical recipient email.
        - otp_code is the raw generated OTP.
        - verification_link_url is the localized resume link for this challenge.
      postconditions:
        - Returns one localized plain-text/email payload for the send capability including the OTP and secure resume link.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The same token should support both immediate same-browser continuation and later recovery from the email itself.
      WHEN TO USE it:
        - Use it right before the Resend send capability for signup and resend.
      WHEN NOT TO USE it:
        - Do not use it for marketing broadcasts or confirmed-user newsletters.
      WHAT CAN GO WRONG:
        - Locale drift can produce the fallback English copy.
      WHAT COMES NEXT:
        - The user can either paste the OTP immediately or open the verification link later on any device.

    TESTS:
      - english_delivery_draft_contains_otp_and_resume_link
      - spanish_delivery_draft_contains_otp_and_resume_link

    ERRORS: []

    CODE:
    """
    base_draft = build_public_email_signup_otp_email_draft(
        language_code=language_code,
        normalized_email=normalized_email,
        otp_code=otp_code,
    )

    if language_code == "es":
        link_line = f"\n\nContinúa la verificación aquí:\n{verification_link_url}"
    else:
        link_line = f"\n\nContinue verification here:\n{verification_link_url}"

    return {
        **base_draft,
        "text_body": f"{base_draft['text_body']}{link_line}",
        "verification_link_url": verification_link_url,
    }


def hash_public_email_signup_identifier_for_logs(raw_value: str) -> str:
    """
    CONTRACT:
      preconditions:
        - raw_value is one sensitive identifier such as an email or flow token.
      postconditions:
        - Returns one short irreversible log-safe fingerprint.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()[:12]


def _read_allowed_public_email_signup_origins() -> set[str]:
    """Minimal contract: return the exact allowed origins for the public email-signup flow."""
    configured_origins = {
        candidate.strip()
        for candidate in os.getenv("DCX_PUBLIC_ALLOWED_ORIGINS", "").split(",")
        if candidate.strip() != ""
    }

    if configured_origins:
        return configured_origins

    if _read_public_email_signup_runtime_environment() in {"production", "staging"}:
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_ALLOWED_ORIGINS_MISSING")

    return {
        "http://localhost:4321",
        "http://127.0.0.1:4321",
        "https://dcx-public.pages.dev",
    }


def _normalize_route_path(route_path: str) -> str:
    """Minimal contract: normalize one URL path while preserving explicit locale roots like /es/."""
    if route_path in {"", "/"}:
        return "/"

    if route_path.rstrip("/") == "/es":
        return "/es/"

    return route_path.rstrip("/")


def _read_public_email_signup_secret_key() -> bytes:
    """Minimal contract: return one non-empty secret key for HMAC operations or raise a stable error."""
    configured_secret = os.getenv("DCX_EMAIL_SIGNUP_OTP_SECRET", "").strip()

    if configured_secret == "":
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_SECRET_MISSING")

    return configured_secret.encode("utf-8")


def _verification_path_for_public_email_signup_language(language_code: str) -> str:
    """Minimal contract: return the localized public verification path for the normalized language code."""
    return "/es/users/signup-email/verificar-codigo" if language_code == "es" else "/users/signup-email/verify-otp"


def _read_public_email_signup_runtime_environment() -> str:
    """Minimal contract: return one normalized runtime environment label for the public signup flow."""
    return os.getenv("DCX_ENVIRONMENT", "local").strip().lower() or "local"
