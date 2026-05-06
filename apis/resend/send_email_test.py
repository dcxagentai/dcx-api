"""
CONTEXT:
This file falsifies the low-level Resend adapter for DCX transactional email delivery.
It keeps the provider boundary executable without requiring live provider calls in tests.
"""

import pytest

from apis.resend.send_email import (
    DCX_RESEND_SENDER_PROFILE_MESSAGES,
    send_email_batch_via_resend,
    send_email_via_resend,
)


def test_resend_adapter_builds_test_mode_params_with_explicit_sender_and_override_recipient(monkeypatch) -> None:
    captured_arguments = {}

    def fake_send_email_with_provider(resend_send_params):
        captured_arguments["resend_send_params"] = resend_send_params
        return {"id": "email_123"}

    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("RESEND_TEST_RECIPIENT", "delivered@resend.dev")
    monkeypatch.setenv("RESEND_ALLOW_TEST_RECIPIENT_OVERRIDE", "true")
    monkeypatch.setenv("DCX_ENVIRONMENT", "local")
    monkeypatch.setenv("RESEND_FROM_NAME", "DCX")
    monkeypatch.setenv("RESEND_FROM_EMAIL_TRANSACTIONAL", "team@dcxagent.ai")

    payload = send_email_via_resend(
        email_delivery_draft={
            "recipient_email": "user@example.com",
            "subject": "Subject",
            "text_body": "Hello\n\nBody",
        },
        send_email_with_provider=fake_send_email_with_provider,
    )

    assert captured_arguments["resend_send_params"]["from"] == "DCX <team@dcxagent.ai>"
    assert captured_arguments["resend_send_params"]["to"] == ["delivered@resend.dev"]
    assert payload["provider_message_id"] == "email_123"


def test_resend_adapter_uses_message_sender_email_for_message_profile(monkeypatch) -> None:
    captured_arguments = {}

    def fake_send_email_with_provider(resend_send_params):
        captured_arguments["resend_send_params"] = resend_send_params
        return {"id": "email_message"}

    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("RESEND_FROM_NAME", "DCX")
    monkeypatch.setenv("RESEND_FROM_EMAIL_MESSAGES", "chat@dcxagent.ai")
    monkeypatch.delenv("RESEND_TEST_RECIPIENT", raising=False)

    payload = send_email_via_resend(
        email_delivery_draft={
            "recipient_email": "user@example.com",
            "subject": "Subject",
            "text_body": "Hello\n\nBody",
        },
        sender_profile=DCX_RESEND_SENDER_PROFILE_MESSAGES,
        send_email_with_provider=fake_send_email_with_provider,
    )

    assert captured_arguments["resend_send_params"]["from"] == "DCX <chat@dcxagent.ai>"
    assert payload["provider_message_id"] == "email_message"


def test_resend_adapter_returns_provider_message_id_when_provider_accepts_send(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("RESEND_FROM_EMAIL_TRANSACTIONAL", "team@dcxagent.ai")
    monkeypatch.setenv("RESEND_FROM_NAME", "DCX")
    monkeypatch.delenv("RESEND_TEST_RECIPIENT", raising=False)

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


def test_resend_batch_adapter_returns_provider_message_ids_in_order(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test_key")
    monkeypatch.setenv("RESEND_FROM_NAME", "DCX")
    monkeypatch.setenv("RESEND_FROM_EMAIL_TRANSACTIONAL", "team@dcxagent.ai")

    captured_batch_params = {}

    def fake_batch_send(batch_params):
        captured_batch_params["batch_params"] = batch_params
        return {"data": [{"id": "email_1"}, {"id": "email_2"}]}

    payload = send_email_batch_via_resend(
        [
            {
                "recipient_email": "alpha@example.com",
                "subject": "Alpha",
                "text_body": "Hello Alpha",
                "html_body": "<p>Hello Alpha</p>",
            },
            {
                "recipient_email": "beta@example.com",
                "subject": "Beta",
                "text_body": "Hello Beta",
                "html_body": "<p>Hello Beta</p>",
            },
        ],
        send_batch_with_provider=fake_batch_send,
    )

    assert captured_batch_params["batch_params"][0]["to"] == ["alpha@example.com"]
    assert captured_batch_params["batch_params"][1]["to"] == ["beta@example.com"]
    assert payload == [
        {"provider": "resend", "status": "accepted", "provider_message_id": "email_1"},
        {"provider": "resend", "status": "accepted", "provider_message_id": "email_2"},
    ]


def test_resend_adapter_prefers_explicit_html_body_when_present(monkeypatch) -> None:
    captured_arguments = {}

    def fake_send_email_with_provider(resend_send_params):
        captured_arguments["resend_send_params"] = resend_send_params
        return {"id": "email_789"}

    monkeypatch.setenv("RESEND_API_KEY", "test-api-key")
    monkeypatch.setenv("RESEND_FROM_NAME", "DCX")
    monkeypatch.setenv("RESEND_FROM_EMAIL_TRANSACTIONAL", "team@dcxagent.ai")
    monkeypatch.delenv("RESEND_TEST_RECIPIENT", raising=False)

    payload = send_email_via_resend(
        {
            "recipient_email": "user@example.com",
            "subject": "Newsletter",
            "text_body": "Plain text body",
            "html_body": "<div><p>Rendered html body</p></div>",
        },
        send_email_with_provider=fake_send_email_with_provider,
    )

    assert captured_arguments["resend_send_params"]["html"] == "<div><p>Rendered html body</p></div>"
    assert payload["provider_message_id"] == "email_789"


def test_resend_adapter_raises_clear_error_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("RESEND_FROM_NAME", "DCX")
    monkeypatch.setenv("RESEND_FROM_EMAIL_TRANSACTIONAL", "team@dcxagent.ai")

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
    monkeypatch.delenv("RESEND_FROM_NAME", raising=False)
    monkeypatch.setenv("RESEND_FROM_EMAIL_TRANSACTIONAL", "team@dcxagent.ai")

    with pytest.raises(
        RuntimeError,
        match="API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:RESEND_FROM_NAME",
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
    monkeypatch.setenv("RESEND_FROM_NAME", "DCX")
    monkeypatch.delenv("RESEND_FROM_EMAIL_TRANSACTIONAL", raising=False)

    with pytest.raises(
        RuntimeError,
        match="API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:RESEND_FROM_EMAIL_TRANSACTIONAL",
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
    monkeypatch.setenv("RESEND_FROM_NAME", "DCX")
    monkeypatch.setenv("RESEND_FROM_EMAIL_TRANSACTIONAL", "team@dcxagent.ai")

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
