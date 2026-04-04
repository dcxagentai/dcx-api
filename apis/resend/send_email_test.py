"""
CONTEXT:
This file falsifies the low-level Resend adapter for DCX transactional email delivery.
It keeps the provider boundary executable without requiring live provider calls in tests.
"""

import pytest

from apis.resend.send_email import send_email_via_resend


def test_resend_adapter_builds_test_mode_params_with_explicit_sender_and_override_recipient(monkeypatch) -> None:
    captured_arguments = {}

    def fake_send_email_with_provider(resend_send_params):
        captured_arguments["resend_send_params"] = resend_send_params
        return {"id": "email_123"}

    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT", "delivered@resend.dev")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE", "true")
    monkeypatch.setenv("DCX_ENVIRONMENT", "local")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_NAME", "DCX")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL", "onboarding@resend.dev")

    payload = send_email_via_resend(
        email_delivery_draft={
            "recipient_email": "user@example.com",
            "subject": "Subject",
            "text_body": "Hello\n\nBody",
        },
        send_email_with_provider=fake_send_email_with_provider,
    )

    assert captured_arguments["resend_send_params"]["from"] == "DCX <onboarding@resend.dev>"
    assert captured_arguments["resend_send_params"]["to"] == ["delivered@resend.dev"]
    assert payload["provider_message_id"] == "email_123"


def test_resend_adapter_returns_provider_message_id_when_provider_accepts_send(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL", "onboarding@resend.dev")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_NAME", "DCX")
    monkeypatch.delenv("DCX_EMAIL_SIGNUP_RESEND_TEST_RECIPIENT", raising=False)

    payload = send_email_via_resend(
        email_delivery_draft={
            "recipient_email": "user@example.com",
            "subject": "Subject",
            "text_body": "Hello\n\nBody",
        },
        send_email_with_provider=lambda *_args: {"id": "email_456"},
    )

    assert payload == {
        "provider": "resend",
        "status": "accepted",
        "provider_message_id": "email_456",
    }


def test_resend_adapter_raises_clear_error_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_NAME", "DCX")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL", "onboarding@resend.dev")

    with pytest.raises(
        RuntimeError,
        match="API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:RESEND_API_KEY",
    ):
        send_email_via_resend(
            email_delivery_draft={
                "recipient_email": "user@example.com",
                "subject": "Subject",
                "text_body": "Hello\n\nBody",
            },
            send_email_with_provider=lambda *_args: {"id": "email_456"},
        )


def test_resend_adapter_raises_clear_error_when_sender_name_missing(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.delenv("DCX_EMAIL_SIGNUP_RESEND_FROM_NAME", raising=False)
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL", "onboarding@resend.dev")

    with pytest.raises(
        RuntimeError,
        match="API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:DCX_EMAIL_SIGNUP_RESEND_FROM_NAME",
    ):
        send_email_via_resend(
            email_delivery_draft={
                "recipient_email": "user@example.com",
                "subject": "Subject",
                "text_body": "Hello\n\nBody",
            },
            send_email_with_provider=lambda *_args: {"id": "email_456"},
        )


def test_resend_adapter_raises_clear_error_when_sender_email_missing(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_NAME", "DCX")
    monkeypatch.delenv("DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL", raising=False)

    with pytest.raises(
        RuntimeError,
        match="API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL",
    ):
        send_email_via_resend(
            email_delivery_draft={
                "recipient_email": "user@example.com",
                "subject": "Subject",
                "text_body": "Hello\n\nBody",
            },
            send_email_with_provider=lambda *_args: {"id": "email_456"},
        )


def test_resend_adapter_raises_clear_error_when_required_draft_fields_are_missing(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_NAME", "DCX")
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL", "onboarding@resend.dev")

    with pytest.raises(
        RuntimeError,
        match="API_PUBLIC_EMAIL_SIGNUP_RESEND_DRAFT_INVALID:subject,text_body",
    ):
        send_email_via_resend(
            email_delivery_draft={
                "recipient_email": "user@example.com",
                "subject": " ",
            },
            send_email_with_provider=lambda *_args: {"id": "email_456"},
        )
