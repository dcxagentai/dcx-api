from users.account_phone.set_authenticated_dcx_user_primary_phone_contact_method import (
    set_authenticated_dcx_user_primary_phone_contact_method,
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


def test_verified_phone_becomes_primary_and_existing_primary_is_demoted() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (44,),
            (302, False, True),
        ]
    )

    result = set_authenticated_dcx_user_primary_phone_contact_method(
        authenticated_user_id=44,
        phone_contact_method_id=302,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1776000010000,
    )

    assert result == {
        "status": "primary_updated",
        "phone_contact_method_id": 302,
    }
    assert any(
        "SET\n                        is_primary = FALSE" in sql
        for sql, _ in fake_connection.cursor_instance.executed_statements
    )
    assert any(
        "SET\n                        is_primary = TRUE" in sql
        for sql, _ in fake_connection.cursor_instance.executed_statements
    )


def test_unverified_phone_cannot_become_primary() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (44,),
            (302, False, False),
        ]
    )

    try:
        set_authenticated_dcx_user_primary_phone_contact_method(
            authenticated_user_id=44,
            phone_contact_method_id=302,
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1776000010000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_VERIFIED"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected unverified phone row to be rejected as primary.")
