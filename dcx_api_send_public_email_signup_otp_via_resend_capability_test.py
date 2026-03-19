"""
CONTEXT:
This file falsifies the Resend delivery capability for the public DCX email-signup OTP flow.
It keeps the provider boundary executable without requiring live provider calls in tests.
"""

import pytest

from dcx_api_send_public_email_signup_otp_via_resend_capability import (
    send_public_email_signup_otp_via_resend_capability,
)


def test_builds_test_mode_params_with_default_sender_and_override_recipient(monkeypatch) -> None:
    captured_arguments = {}

    def fake_send_email_via_resend(resend_api_key, resend_send_params):
        captured_arguments["resend_api_key"] = resend_api_key
        captured_arguments["resend_send_params"] = resend_send_params
        return {"id": "email_123"}

    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT", "delivered@resend.dev")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE", "true")
    monkeypatch.setenv("DCX_ENVIRONMENT", "local")

    payload = send_public_email_signup_otp_via_resend_capability(
        email_delivery_draft={
            "recipient_email": "user@example.com",
            "subject": "Your DCX access code",
            "text_body": "Hello\n\nYour code is 123456",
        },
        challenge_id=301,
        send_email_via_resend=fake_send_email_via_resend,
    )

    assert captured_arguments["resend_api_key"] == "test_key"
    assert captured_arguments["resend_send_params"]["from"] == "DCX <onboarding@resend.dev>"
    assert captured_arguments["resend_send_params"]["to"] == ["delivered@resend.dev"]
    assert payload["provider_message_id"] == "email_123"


def test_returns_internal_delivery_summary_when_provider_accepts_send(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL", "onboarding@resend.dev")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_NAME", "DCX")
    monkeypatch.delenv("DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT", raising=False)

    payload = send_public_email_signup_otp_via_resend_capability(
        email_delivery_draft={
            "recipient_email": "user@example.com",
            "subject": "Your DCX access code",
            "text_body": "Hello\n\nYour code is 123456",
        },
        challenge_id=301,
        send_email_via_resend=lambda *_: {"id": "email_456"},
    )

    assert payload == {
        "provider": "resend",
        "status": "accepted",
        "challenge_id": 301,
        "provider_message_id": "email_456",
    }


def test_raises_clear_error_when_resend_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_RESEND_API_KEY_MISSING"):
        send_public_email_signup_otp_via_resend_capability(
            email_delivery_draft={
                "recipient_email": "user@example.com",
                "subject": "Your DCX access code",
                "text_body": "Hello\n\nYour code is 123456",
            },
            challenge_id=301,
            send_email_via_resend=lambda *_: {"id": "email_456"},
        )


def test_rejects_test_recipient_override_without_explicit_local_flag(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT", "delivered@resend.dev")
    monkeypatch.delenv("DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE", raising=False)

    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN"):
        send_public_email_signup_otp_via_resend_capability(
            email_delivery_draft={
                "recipient_email": "user@example.com",
                "subject": "Your DCX access code",
                "text_body": "Hello\n\nYour code is 123456",
            },
            challenge_id=301,
            send_email_via_resend=lambda *_: {"id": "email_456"},
        )


def test_rejects_test_recipient_override_outside_local_even_with_flag(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT", "delivered@resend.dev")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE", "true")
    monkeypatch.setenv("DCX_ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN"):
        send_public_email_signup_otp_via_resend_capability(
            email_delivery_draft={
                "recipient_email": "user@example.com",
                "subject": "Your DCX access code",
                "text_body": "Hello\n\nYour code is 123456",
            },
            challenge_id=301,
            send_email_via_resend=lambda *_: {"id": "email_456"},
        )


def test_rejects_test_recipient_override_when_runtime_environment_is_unset(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT", "delivered@resend.dev")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE", "true")
    monkeypatch.delenv("DCX_ENVIRONMENT", raising=False)

    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN"):
        send_public_email_signup_otp_via_resend_capability(
            email_delivery_draft={
                "recipient_email": "user@example.com",
                "subject": "Your DCX access code",
                "text_body": "Hello\n\nYour code is 123456",
            },
            challenge_id=301,
            send_email_via_resend=lambda *_: {"id": "email_456"},
        )
