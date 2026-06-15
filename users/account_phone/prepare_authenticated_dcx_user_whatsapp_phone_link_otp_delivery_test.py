from users.account_phone.prepare_authenticated_dcx_user_whatsapp_phone_link_delivery import (
    prepare_authenticated_dcx_user_whatsapp_phone_link_delivery,
)


class _FakeCursor:
    def __init__(self, fetchone_results):
        self._fetchone_results = list(fetchone_results)
        self.executed_statements = []

    def execute(self, sql, params=None):
        self.executed_statements.append((sql, params))

    def fetchone(self):
        if not self._fetchone_results:
            return None
        return self._fetchone_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, fetchone_results):
        self.cursor_instance = _FakeCursor(fetchone_results)

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_prepares_new_pending_whatsapp_phone_link_for_valid_phone(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (44,),
            None,
            (3001, "whatsapp", "meta_whatsapp", "", "local:meta_whatsapp_default", "", "", "local", "active"),
            None,
            None,
            (701,),
            None,
            (901,),
            (1001,),
        ]
    )

    result = prepare_authenticated_dcx_user_whatsapp_phone_link_delivery(
        authenticated_user_id=44,
        candidate_phone_number="+34 600 000 001",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1776000000000,
        raw_token_provider=lambda: "whatsapp-phone-link-token-value-1234567890",
    )

    assert result == {
        "status": "pending_verification",
        "send_required": True,
        "challenge_id": 901,
        "confirmation_id": 1001,
        "contact_method_id": 701,
        "phone_e164": "+34600000001",
        "channel_origin": {
            "id": 3001,
            "channel_type": "whatsapp",
            "provider_type": "meta_whatsapp",
            "provider_account_id": "",
            "provider_sender_id": "local:meta_whatsapp_default",
            "sender_display_handle": "",
            "sender_display_name": "",
            "environment_key": "local",
            "origin_status": "active",
        },
        "raw_phone_link_token": "whatsapp-phone-link-token-value-1234567890",
        "verification_link_suffix": "en/t/verify-whatsapp-phone#whatsapp_phone_link_token=whatsapp-phone-link-token-value-1234567890",
        "verification_link_url": "http://localhost:5173/en/t/verify-whatsapp-phone#whatsapp_phone_link_token=whatsapp-phone-link-token-value-1234567890",
    }


def test_already_confirmed_whatsapp_phone_returns_without_send(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (44,),
            (55, True, 888),
            (3001, "whatsapp", "meta_whatsapp", "", "local:meta_whatsapp_default", "", "", "local", "active"),
            (1001, "confirmed", 1776000000000),
        ]
    )

    result = prepare_authenticated_dcx_user_whatsapp_phone_link_delivery(
        authenticated_user_id=44,
        candidate_phone_number="+34600000001",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1776000000000,
    )

    assert result == {
        "status": "already_confirmed",
        "send_required": False,
        "phone_e164": "+34600000001",
        "contact_method_id": 55,
        "channel_origin": {
            "id": 3001,
            "channel_type": "whatsapp",
            "provider_type": "meta_whatsapp",
            "provider_account_id": "",
            "provider_sender_id": "local:meta_whatsapp_default",
            "sender_display_handle": "",
            "sender_display_name": "",
            "environment_key": "local",
            "origin_status": "active",
        },
        "channel_origin_confirmation": {
            "id": 1001,
            "confirmation_status": "confirmed",
            "confirmed_at_ts_ms": 1776000000000,
        },
    }


def test_raises_when_phone_is_already_linked_to_another_user(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (44,),
            None,
            (3001, "whatsapp", "meta_whatsapp", "", "local:meta_whatsapp_default", "", "", "local", "active"),
            (91,),
        ]
    )

    try:
        prepare_authenticated_dcx_user_whatsapp_phone_link_delivery(
            authenticated_user_id=44,
            candidate_phone_number="+34600000001",
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1776000000000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected other-user phone conflict to raise a stable runtime error.")


def test_enforces_send_cooldown_for_active_delivered_challenge(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (44,),
            None,
            (3001, "whatsapp", "meta_whatsapp", "", "local:meta_whatsapp_default", "", "", "local", "active"),
            None,
            None,
            (701,),
            (901, "+34600000001", 1776000000000, 1776000030000, 0, 1, 1776000000000, 1),
        ]
    )

    try:
        prepare_authenticated_dcx_user_whatsapp_phone_link_delivery(
            authenticated_user_id=44,
            candidate_phone_number="+34600000001",
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1776000010000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_SEND_COOLDOWN_ACTIVE"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected active cooldown to raise a stable runtime error.")
