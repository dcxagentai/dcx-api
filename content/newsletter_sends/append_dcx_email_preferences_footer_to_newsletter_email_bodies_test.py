from content.newsletter_sends.append_dcx_email_preferences_footer_to_newsletter_email_bodies import (
    append_dcx_email_preferences_footer_to_newsletter_email_bodies,
)


def test_appends_three_unsubscribe_links_to_rendered_bodies(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    monkeypatch.setenv("DCX_API_BASE_URL", "https://api.example.com")

    payload = append_dcx_email_preferences_footer_to_newsletter_email_bodies(
        rendered_bodies={"text_body": "Hello", "html_body": "<div><p>Hello</p></div>"},
        user_id=7,
        recipient_email="alpha@example.com",
        current_timestamp_ms_provider=lambda: 1778000000000,
    )

    assert "Unsubscribe from all email: https://api.example.com/public/email-preferences/unsubscribe/all/" in payload["text_body"]
    assert "Unsubscribe from promotional email: https://api.example.com/public/email-preferences/unsubscribe/promotional/" in payload["text_body"]
    assert "Unsubscribe from newsletters: https://api.example.com/public/email-preferences/unsubscribe/newsletters/" in payload["text_body"]
    assert "<a href=\"https://api.example.com/public/email-preferences/unsubscribe/all/" in payload["html_body"]
