from emails.transactional.build_dcx_password_reset_email_delivery_draft import (
    build_dcx_password_reset_email_delivery_draft,
)


def test_builds_password_reset_draft_from_live_template(monkeypatch) -> None:
    monkeypatch.setattr(
        "emails.transactional.build_dcx_password_reset_email_delivery_draft.read_live_email_template_capability",
        lambda **_: {
            "email_subject": "Reset your password",
            "email_body": "Use {{ password_set_url }}",
        },
    )

    payload = build_dcx_password_reset_email_delivery_draft(
        language_code="en",
        normalized_email="user@example.com",
        password_set_url="https://app.example.com/password/set",
    )

    assert payload["subject"] == "Reset your password"
    assert payload["text_body"] == "Use https://app.example.com/password/set"


def test_falls_back_to_inline_english_when_live_template_missing(monkeypatch) -> None:
    def _raise_missing_template(**_):
        raise RuntimeError("API_LIVE_EMAIL_TEMPLATE_NOT_FOUND")

    monkeypatch.setattr(
        "emails.transactional.build_dcx_password_reset_email_delivery_draft.read_live_email_template_capability",
        _raise_missing_template,
    )

    payload = build_dcx_password_reset_email_delivery_draft(
        language_code="en",
        normalized_email="user@example.com",
        password_set_url="https://app.example.com/password/set",
    )

    assert payload["recipient_email"] == "user@example.com"
    assert "https://app.example.com/password/set" in payload["text_body"]
