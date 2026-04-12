"""
CONTEXT:
This file falsifies the public DCX email-signup request acceptance capability.
It keeps the strict browser-facing request contract executable next to the capability.
"""

import pytest

from users.signup_email.accept_public_email_signup_request import (
    accept_public_email_signup_request_capability,
)


def test_valid_request_returns_normalized_payload() -> None:
    payload = accept_public_email_signup_request_capability(
        email=" USER@Example.COM ",
        language_code=" EN ",
        signup_page_url="http://localhost:4321/?email=leak@example.com#anchor",
        origin_header="http://localhost:4321",
        read_allowed_signup_page_paths=lambda: {"/"},
    )

    assert payload == {
        "normalized_email": "user@example.com",
        "language_code": "en",
        "origin_header": "http://localhost:4321",
        "signup_page_url": "http://localhost:4321/",
    }


def test_rejects_unknown_origin() -> None:
    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_ORIGIN_INVALID"):
        accept_public_email_signup_request_capability(
            email="user@example.com",
            language_code="en",
            signup_page_url="https://evil.example.com/",
            origin_header="https://evil.example.com",
            read_allowed_signup_page_paths=lambda: {"/"},
        )


def test_rejects_unknown_signup_path() -> None:
    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_PAGE_URL_INVALID"):
        accept_public_email_signup_request_capability(
            email="user@example.com",
            language_code="en",
            signup_page_url="http://localhost:4321/users/signup-email/verify-otp",
            origin_header="http://localhost:4321",
            read_allowed_signup_page_paths=lambda: {"/"},
        )


def test_invalid_email_raises_specific_error() -> None:
    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_EMAIL_INVALID"):
        accept_public_email_signup_request_capability(
            email="not-an-email",
            language_code="en",
            signup_page_url="http://localhost:4321/",
            origin_header="http://localhost:4321",
            read_allowed_signup_page_paths=lambda: {"/"},
        )


def test_accepts_published_content_article_path() -> None:
    payload = accept_public_email_signup_request_capability(
        email="user@example.com",
        language_code="en",
        signup_page_url="http://localhost:4321/en/insights/live-test-page?utm_source=share#cta",
        origin_header="http://localhost:4321",
        read_allowed_signup_page_paths=lambda: {"/", "/en/insights/live-test-page"},
    )

    assert payload["signup_page_url"] == "http://localhost:4321/en/insights/live-test-page"


def test_surfaces_allowed_paths_reader_failure() -> None:
    def _raise_allowed_paths_failure() -> set[str]:
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_ALLOWED_PATHS_UNAVAILABLE")

    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_ALLOWED_PATHS_UNAVAILABLE"):
        accept_public_email_signup_request_capability(
            email="user@example.com",
            language_code="en",
            signup_page_url="http://localhost:4321/",
            origin_header="http://localhost:4321",
            read_allowed_signup_page_paths=_raise_allowed_paths_failure,
        )
