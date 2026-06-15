from users.account_phone.remove_authenticated_dcx_user_phone_contact_method import (
    remove_authenticated_dcx_user_phone_contact_method,
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


def test_removes_unused_non_primary_phone_contact_method() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (22, "+34600000001", False),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (22,),
        ]
    )

    result = remove_authenticated_dcx_user_phone_contact_method(
        authenticated_user_id=44,
        phone_contact_method_id=22,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1776000000000,
    )

    assert result == {
        "status": "removed",
        "phone_contact_method_id": 22,
    }
    assert any("is_active = FALSE" in statement[0] for statement in fake_connection.cursor_instance.executed_statements)
    assert any(
        "UPDATE stephen_dcx_user_auth_challenges" in statement[0]
        for statement in fake_connection.cursor_instance.executed_statements
    )


def test_blocks_removing_primary_phone_contact_method() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (22, "+34600000001", True),
        ]
    )

    try:
        remove_authenticated_dcx_user_phone_contact_method(
            authenticated_user_id=44,
            phone_contact_method_id=22,
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1776000000000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_REMOVE_BLOCKED_PRIMARY"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected primary phone removal to be blocked.")


def test_blocks_removing_phone_contact_method_with_auth_identity() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (22, "+34600000001", False),
            (1,),
        ]
    )

    try:
        remove_authenticated_dcx_user_phone_contact_method(
            authenticated_user_id=44,
            phone_contact_method_id=22,
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1776000000000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_REMOVE_BLOCKED:auth_identity"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected phone removal with auth identity to be blocked.")
