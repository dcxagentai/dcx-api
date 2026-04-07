from emails.transactional.send_dcx_password_reset_email import send_dcx_password_reset_email


def test_password_reset_send_returns_delivery_summary_when_provider_accepts() -> None:
    payload = send_dcx_password_reset_email(
        email_delivery_draft={
            "provider": "resend",
            "recipient_email": "user@example.com",
            "subject": "Reset",
            "text_body": "Use the link",
        },
        send_email=lambda _: {
            "provider": "resend",
            "status": "accepted",
            "provider_message_id": "msg_123",
        },
    )

    assert payload["status"] == "accepted"
