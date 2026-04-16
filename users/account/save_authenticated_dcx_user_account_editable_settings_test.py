from users.account.save_authenticated_dcx_user_account_editable_settings import (
    save_authenticated_dcx_user_account_editable_settings_capability,
)


class _FakeCursor:
    def __init__(self, fetchone_results):
        self._fetchone_results = list(fetchone_results)
        self.executed_queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params):
        self.executed_queries.append((query, params))

    def fetchone(self):
        if not self._fetchone_results:
            return None
        return self._fetchone_results.pop(0)


class _FakeConnection:
    def __init__(self, fetchone_results):
        self._fetchone_results = fetchone_results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._fetchone_results)


def test_saves_editable_settings_via_direct_user_row_update() -> None:
    result = save_authenticated_dcx_user_account_editable_settings_capability(
        authenticated_user_id=5,
        preferred_language_id=4,
        preferred_timezone_id=2,
        email_communication_preference="announcements",
        connect_to_database=lambda **_: _FakeConnection([(1,), (1,), (5, 4, 2, "announcements")]),
    )

    assert result == {
        "user_id": 5,
        "preferred_language_id": 4,
        "preferred_timezone_id": 2,
        "email_communication_preference": "announcements",
    }


def test_raises_clear_error_for_invalid_email_communication_preference() -> None:
    try:
        save_authenticated_dcx_user_account_editable_settings_capability(
            authenticated_user_id=5,
            preferred_language_id=4,
            preferred_timezone_id=2,
            email_communication_preference="marketing_everything",
            connect_to_database=lambda **_: _FakeConnection([(1,), (1,), (5, 4, 2, "announcements")]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_ACCOUNT_EMAIL_PREFERENCE_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid email preference to raise a stable runtime error.")


def test_raises_clear_error_for_missing_user_row() -> None:
    try:
        save_authenticated_dcx_user_account_editable_settings_capability(
            authenticated_user_id=5,
            preferred_language_id=None,
            preferred_timezone_id=None,
            email_communication_preference="essential_only",
            connect_to_database=lambda **_: _FakeConnection([None]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected missing-user save to raise a stable runtime error.")


def test_raises_clear_error_for_invalid_timezone() -> None:
    try:
        save_authenticated_dcx_user_account_editable_settings_capability(
            authenticated_user_id=5,
            preferred_language_id=4,
            preferred_timezone_id=-1,
            email_communication_preference="announcements",
            connect_to_database=lambda **_: _FakeConnection([(1,), (1,), (5, 4, 2, "announcements")]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_ACCOUNT_TIMEZONE_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid timezone to raise a stable runtime error.")
