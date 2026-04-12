"""
CONTEXT:
This file validates and normalizes the first public DCX email-signup request.
It exists so the `/users/signup-email` boundary accepts only the exact payload shape,
origin, and landing-page routes we allow before any database mutation or email send happens.
"""

from __future__ import annotations

from typing import Callable

from users.signup_email.read_allowed_public_email_signup_page_paths import (
    read_allowed_public_email_signup_page_paths,
)
from users.signup_email.public_email_signup_otp_support import (
    normalize_public_email_signup_email,
    normalize_public_email_signup_language_code,
    normalize_public_email_signup_origin_header,
    normalize_public_email_signup_page_url,
)


def accept_public_email_signup_request_capability(
    email: str,
    language_code: str,
    signup_page_url: str,
    origin_header: str | None,
    read_allowed_signup_page_paths: Callable[[], set[str]] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email, language_code, and signup_page_url came from the public signup form.
        - origin_header is the browser Origin header for the request.
      postconditions:
        - Returns one normalized payload containing canonical email, language, origin, and signup page URL values.
        - Rejects missing or unknown origins.
        - Rejects page URLs outside the currently allowed public signup source paths.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The public signup boundary should be exact and boring: known fields, known origin, and known
          public route shapes backed by the live published site state.
      WHEN TO USE it:
        - Use it at the start of `/users/signup-email`.
      WHEN NOT TO USE it:
        - Do not use it for OTP verification or resend requests.
      WHAT CAN GO WRONG:
        - The browser can send a malformed email or page URL.
        - The request can come from an unknown origin.
        - The submitted public page URL can point at a route we do not currently publish.
        - The published-path reader can fail while backend dependencies are unhealthy.
      WHAT COMES NEXT:
        - The persistence capability can build user, identity, and challenge state from this normalized payload.

    TESTS:
      - valid_request_returns_normalized_payload
      - strips_query_string_and_fragment_from_signup_page_url
      - rejects_unknown_origin
      - rejects_unknown_signup_path
      - rejects_invalid_email

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_ORIGIN_INVALID:
          suggested_action: Retry the request from the official DCX public site.
          common_causes:
            - missing Origin header
            - unknown frontend host
          recovery_steps:
            - Reopen the official DCX public site.
            - Retry the request from that page.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_EMAIL_MISSING:
          suggested_action: Enter an email address and try again.
          common_causes:
            - empty or whitespace-only input
          recovery_steps:
            - Fill the email field.
            - Retry the request.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_EMAIL_INVALID:
          suggested_action: Correct the email format and try again.
          common_causes:
            - malformed email address
          recovery_steps:
            - Enter a conventional email address.
            - Retry the request.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_LANGUAGE_CODE_INVALID:
          suggested_action: Reload the localized public page and retry.
          common_causes:
            - malformed locale value
          recovery_steps:
            - Reopen the public page.
            - Retry the request.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_PAGE_URL_INVALID:
          suggested_action: Retry the request from an official DCX signup page.
          common_causes:
            - relative URL
            - unapproved route path
            - origin mismatch
          recovery_steps:
            - Reload the public landing page.
            - Retry the request.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_ALLOWED_PATHS_UNAVAILABLE:
          suggested_action: Retry in a moment after the backend recovers.
          common_causes:
            - database connectivity failure while reading published content routes
            - route allowlist reader failure
          recovery_steps:
            - Wait a little.
            - Retry the signup request from the official public site.
          retry_safe: true

    CODE:
    """
    read_signup_paths = read_allowed_signup_page_paths or read_allowed_public_email_signup_page_paths
    normalized_origin = normalize_public_email_signup_origin_header(origin_header)
    normalized_email = normalize_public_email_signup_email(
        email=email,
        missing_error_code="API_PUBLIC_EMAIL_SIGNUP_EMAIL_MISSING",
        invalid_error_code="API_PUBLIC_EMAIL_SIGNUP_EMAIL_INVALID",
    )
    normalized_language_code = normalize_public_email_signup_language_code(
        language_code=language_code,
        invalid_error_code="API_PUBLIC_EMAIL_SIGNUP_LANGUAGE_CODE_INVALID",
    )
    normalized_signup_page_url = normalize_public_email_signup_page_url(
        page_url=signup_page_url,
        expected_origin=normalized_origin,
        allowed_paths=read_signup_paths(),
        invalid_error_code="API_PUBLIC_EMAIL_SIGNUP_PAGE_URL_INVALID",
    )

    return {
        "normalized_email": normalized_email,
        "language_code": normalized_language_code,
        "origin_header": normalized_origin,
        "signup_page_url": normalized_signup_page_url,
    }
