from users.account_phone.verify_dcx_whatsapp_phone_link_from_challenge_token import (
    verify_dcx_whatsapp_phone_link_from_challenge_token,
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


def test_correct_otp_links_phone_and_consumes_pending_challenge(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                901,
                44,
                "+34600000001",
                1776000600000,
                1776000000000,
                "pending",
            ),
            None,
            None,
            None,
            None,
            (301,),
            None,
            (401,),
        ]
    )

    result = verify_dcx_whatsapp_phone_link_from_challenge_token(
        raw_phone_link_token="whatsapp-phone-link-token-value-1234567890",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1776000010000,
    )

    assert result == {
        "status": "verified",
        "phone_e164": "+34600000001",
        "whatsapp_identity_id": 401,
        "user_id": 44,
        "verified_at_ts_ms": 1776000010000,
    }


def test_incorrect_otp_increments_attempt_count(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")

    try:
        verify_dcx_whatsapp_phone_link_from_challenge_token(
            raw_phone_link_token="too-short",
            connect_to_database=lambda **_: _FakeConnection(fetchone_results=[]),
            current_timestamp_ms_provider=lambda: 1776000010000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_WHATSAPP_PHONE_LINK_TOKEN_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid token to raise a stable runtime error.")


def test_duplicate_phone_conflict_after_send_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                901,
                44,
                "+34600000001",
                1776000600000,
                1776000000000,
                "pending",
            ),
            (91,),
        ]
    )

    try:
        verify_dcx_whatsapp_phone_link_from_challenge_token(
            raw_phone_link_token="whatsapp-phone-link-token-value-1234567890",
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1776000010000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected phone conflict to raise a stable runtime error.")


def test_verified_new_phone_does_not_auto_replace_existing_primary(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                901,
                44,
                "+34600000002",
                1776000600000,
                1776000000000,
                "pending",
            ),
            None,
            None,
            (111,),
            None,
            (302,),
            None,
            (401,),
        ]
    )

    result = verify_dcx_whatsapp_phone_link_from_challenge_token(
        raw_phone_link_token="whatsapp-phone-link-token-value-1234567890",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1776000010000,
    )

    assert result["status"] == "verified"
    insert_statement = next(
        statement
        for statement in fake_connection.cursor_instance.executed_statements
        if "INSERT INTO stephen_dcx_users_contact_methods" in statement[0]
    )
    assert insert_statement[1][5] is False
