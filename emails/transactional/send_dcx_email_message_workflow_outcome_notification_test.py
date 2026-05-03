import pytest

from emails.transactional import send_dcx_email_message_workflow_outcome_notification as module_under_test


def test_sends_one_outcome_email(monkeypatch) -> None:
    sent_emails: list[dict] = []

    def fake_send_email_via_resend(email_delivery_draft: dict, sender_profile: str) -> dict:
        sent_emails.append(
            {
                "email_delivery_draft": email_delivery_draft,
                "sender_profile": sender_profile,
            }
        )
        return {
            "provider": "resend",
            "status": "accepted",
            "provider_message_id": "email_123",
        }

    monkeypatch.setattr(module_under_test, "send_email_via_resend", fake_send_email_via_resend)

    result = module_under_test.send_dcx_email_message_workflow_outcome_notification(
        recipient_email=" trader@example.com ",
        subject=" DCX found trade candidates ",
        message_text=" DCX processed your message. ",
    )

    assert result["status"] == "accepted"
    assert sent_emails == [
        {
            "email_delivery_draft": {
                "recipient_email": "trader@example.com",
                "subject": "DCX found trade candidates",
                "text_body": "DCX processed your message.",
                "html_body": (
                    '<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.55;color:#111827;'
                    'white-space:pre-wrap;">DCX processed your message.</div>'
                ),
            },
            "sender_profile": module_under_test.DCX_RESEND_SENDER_PROFILE_MESSAGES,
        }
    ]


def test_renders_markdown_links_in_outcome_email_html(monkeypatch) -> None:
    sent_emails: list[dict] = []

    def fake_send_email_via_resend(email_delivery_draft: dict, sender_profile: str) -> dict:
        sent_emails.append(email_delivery_draft)
        return {
            "provider": "resend",
            "status": "accepted",
            "provider_message_id": "email_123",
        }

    monkeypatch.setattr(module_under_test, "send_email_via_resend", fake_send_email_via_resend)

    module_under_test.send_dcx_email_message_workflow_outcome_notification(
        recipient_email="trader@example.com",
        subject="DCX: Topic",
        message_text="Sources:\n- [cbc.ca](https://example.com/cbc)",
    )

    assert '<a href="https://example.com/cbc"' in sent_emails[0]["html_body"]
    assert ">cbc.ca</a>" in sent_emails[0]["html_body"]
    assert sent_emails[0]["text_body"] == "Sources:\n- cbc.ca: https://example.com/cbc"
    assert "[cbc.ca](https://example.com/cbc)" not in sent_emails[0]["text_body"]


def test_renders_markdown_headings_and_bold_as_email_html(monkeypatch) -> None:
    sent_emails: list[dict] = []

    def fake_send_email_via_resend(email_delivery_draft: dict, sender_profile: str) -> dict:
        sent_emails.append(email_delivery_draft)
        return {
            "provider": "resend",
            "status": "accepted",
            "provider_message_id": "email_123",
        }

    monkeypatch.setattr(module_under_test, "send_email_via_resend", fake_send_email_via_resend)

    module_under_test.send_dcx_email_message_workflow_outcome_notification(
        recipient_email="trader@example.com",
        subject="DCX: Topic",
        message_text="### Latest Developments\n\n- **Insurance:** Premiums remain elevated.",
    )

    assert "<strong>Latest Developments</strong>" in sent_emails[0]["html_body"]
    assert "<strong>Insurance:</strong>" in sent_emails[0]["html_body"]
    assert "###" not in sent_emails[0]["text_body"]
    assert "**Insurance:**" not in sent_emails[0]["text_body"]


def test_rejects_blank_inputs() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        module_under_test.send_dcx_email_message_workflow_outcome_notification(
            recipient_email="",
            subject="DCX found trade candidates",
            message_text="DCX processed your message.",
        )

    assert str(exc_info.value) == "API_DCX_EMAIL_WORKFLOW_OUTCOME_MESSAGE_INVALID"
