from users.account.dcx_email_preference_unsubscribe_support import (
    build_dcx_email_preference_unsubscribe_token,
    build_dcx_email_preference_unsubscribe_url,
    read_dcx_email_preference_unsubscribe_token_payload,
)


def test_builds_and_reads_unsubscribe_token_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")

    token = build_dcx_email_preference_unsubscribe_token(
        user_id=7,
        recipient_email="Alpha@Example.com",
        unsubscribe_kind="newsletters",
        current_timestamp_ms_provider=lambda: 1778000000000,
    )

    payload = read_dcx_email_preference_unsubscribe_token_payload(
        token,
        current_timestamp_ms_provider=lambda: 1778000000001,
    )

    assert payload == {
        "user_id": 7,
        "recipient_email": "alpha@example.com",
        "unsubscribe_kind": "newsletters",
        "exp": 1793552000000,
    }


def test_rejects_expired_unsubscribe_token(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")

    token = build_dcx_email_preference_unsubscribe_token(
        user_id=7,
        recipient_email="alpha@example.com",
        unsubscribe_kind="all",
        current_timestamp_ms_provider=lambda: 1778000000000,
    )

    try:
        read_dcx_email_preference_unsubscribe_token_payload(
            token,
            current_timestamp_ms_provider=lambda: 1793552000001,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_EXPIRED"
    else:  # pragma: no cover - guard
        raise AssertionError("Expected expired unsubscribe token error")


def test_builds_unsubscribe_url_against_configured_api_base_url(monkeypatch) -> None:
    monkeypatch.setenv("DCX_API_BASE_URL", "https://api.example.com/")

    assert (
        build_dcx_email_preference_unsubscribe_url(
            "promotional",
            "token-value",
        )
        == "https://api.example.com/public/email-preferences/unsubscribe/promotional/token-value"
    )
