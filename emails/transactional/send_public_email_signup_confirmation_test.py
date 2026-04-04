"""
CONTEXT:
This file falsifies the domain-level public DCX email-signup confirmation delivery function.
It keeps the transactional confirmation purpose executable without requiring live provider calls in tests.
"""

from emails.transactional.send_public_email_signup_confirmation import (
    send_public_email_signup_confirmation,
)


def test_signup_confirmation_send_returns_internal_delivery_summary_when_provider_accepts_send() -> None:
    payload = send_public_email_signup_confirmation(
        email_delivery_draft={
            "recipient_email": "user@example.com",
            "subject": "You're on the DCX Agentic waitlist",
            "text_body": "Hello\n\nThanks for joining.",
        },
        confirmed_email="user@example.com",
        send_email=lambda *_: {
            "provider": "resend",
            "status": "accepted",
            "provider_message_id": "email_456",
        },
    )

    assert payload == {
        "provider": "resend",
        "status": "accepted",
        "confirmed_email": "user@example.com",
        "provider_message_id": "email_456",
    }
