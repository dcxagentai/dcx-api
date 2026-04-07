from auth.password.request_dcx_password_reset_email_challenge import (
    request_dcx_password_reset_email_challenge,
)


def test_returns_generic_acceptance_without_email_draft_for_unknown_user(monkeypatch) -> None:
    monkeypatch.setattr(
        "auth.password.request_dcx_password_reset_email_challenge.read_confirmed_dcx_user_identity_for_password_link_by_email",
        lambda **_: None,
    )

    payload = request_dcx_password_reset_email_challenge(email="unknown@example.com")

    assert payload == {
        "status": "accepted",
        "email_delivery_draft": None,
        "password_set_url": None,
    }


def test_returns_password_reset_email_draft_for_confirmed_user(monkeypatch) -> None:
    monkeypatch.setattr(
        "auth.password.request_dcx_password_reset_email_challenge.read_confirmed_dcx_user_identity_for_password_link_by_email",
        lambda **_: {
            "user_id": 1,
            "primary_email": "user@example.com",
            "user_auth_identity_id": 2,
            "language_code": "en",
        },
    )
    monkeypatch.setattr(
        "auth.password.request_dcx_password_reset_email_challenge.create_or_refresh_dcx_password_link_challenge",
        lambda **_: {
            "password_set_url": "https://app.example.com/password/set",
        },
    )
    monkeypatch.setattr(
        "auth.password.request_dcx_password_reset_email_challenge.build_dcx_password_reset_email_delivery_draft",
        lambda **_: {
            "recipient_email": "user@example.com",
            "subject": "Reset",
            "text_body": "Use the link",
        },
    )

    payload = request_dcx_password_reset_email_challenge(email="user@example.com")

    assert payload["status"] == "accepted"
    assert payload["email_delivery_draft"]["subject"] == "Reset"
