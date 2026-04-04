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
        )


def test_rejects_unknown_signup_path() -> None:
    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_PAGE_URL_INVALID"):
        accept_public_email_signup_request_capability(
            email="user@example.com",
            language_code="en",
            signup_page_url="http://localhost:4321/users/signup-email/verify-otp",
            origin_header="http://localhost:4321",
        )


def test_invalid_email_raises_specific_error() -> None:
    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_EMAIL_INVALID"):
        accept_public_email_signup_request_capability(
            email="not-an-email",
            language_code="en",
            signup_page_url="http://localhost:4321/",
            origin_header="http://localhost:4321",
        )
