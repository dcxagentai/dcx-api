"""
CONTEXT:
This file falsifies the domain-level public DCX email-signup OTP delivery function.
It keeps the transactional email purpose executable without requiring live provider calls in tests.
"""

from emails.transactional.send_public_email_signup_otp import send_public_email_signup_otp


def test_signup_otp_send_returns_internal_delivery_summary_when_provider_accepts_send() -> None:
    payload = send_public_email_signup_otp(
        email_delivery_draft={
            "recipient_email": "user@example.com",
            "subject": "Your DCX access code",
            "text_body": "Hello\n\nYour code is 123456",
        },
        challenge_id=301,
        send_email=lambda *_: {
            "provider": "resend",
            "status": "accepted",
            "provider_message_id": "email_456",
        },
    )

    assert payload == {
        "provider": "resend",
        "status": "accepted",
        "challenge_id": 301,
        "provider_message_id": "email_456",
    }
