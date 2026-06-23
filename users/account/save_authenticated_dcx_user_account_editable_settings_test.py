from users.account.save_authenticated_dcx_user_account_editable_settings import (
    save_authenticated_dcx_user_account_editable_settings_capability,
)


class _FakeCursor:
    def __init__(self, fetchone_results, fetchall_results=None):
        self._fetchone_results = list(fetchone_results)
        self._fetchall_results = list(fetchall_results or [])
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

    def fetchall(self):
        if not self._fetchall_results:
            return []
        return self._fetchall_results.pop(0)


class _FakeConnection:
    def __init__(self, fetchone_results, fetchall_results=None):
        self._fetchone_results = fetchone_results
        self._fetchall_results = fetchall_results or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._fetchone_results, self._fetchall_results)


def test_saves_editable_settings_via_direct_user_row_update() -> None:
    result = save_authenticated_dcx_user_account_editable_settings_capability(
        authenticated_user_id=5,
        preferred_language_id=4,
        preferred_timezone_id=2,
        email_communication_preference="newsletters",
        public_display_name="Stephen Trader",
        public_handle="stephen_trader",
        public_identity_mode="handle",
        default_interaction_channel="email",
        trade_interest_material_keys=["aluminum", "wheat"],
        sidebar_clock_timezone_ids=[1, 2],
        connect_to_database=lambda **_: _FakeConnection(
            [
                None,
                (5, 4, 2, "newsletters", "Stephen Trader", "stephen_trader", "handle", "email", 1, None),
            ],
            [
                [(4,)],
                [(1,), (2,)],
                [("aluminum",), ("wheat",)],
            ],
        ),
    )

    assert result == {
        "user_id": 5,
        "preferred_language_id": 4,
        "preferred_timezone_id": 2,
        "email_communication_preference": "newsletters",
        "public_display_name": "Stephen Trader",
        "public_handle": "stephen_trader",
        "public_identity_mode": "handle",
        "default_interaction_channel": "email",
        "selected_language_ids": [4],
        "selected_timezone_ids": [2, 1],
        "selected_country_ids": [],
        "sidebar_clock_timezone_ids": [1],
        "trade_interest_material_keys": ["aluminum", "wheat"],
    }


def test_raises_clear_error_for_invalid_email_communication_preference() -> None:
    try:
        save_authenticated_dcx_user_account_editable_settings_capability(
            authenticated_user_id=5,
            preferred_language_id=4,
            preferred_timezone_id=2,
            email_communication_preference="marketing_everything",
            public_display_name="Stephen Trader",
            public_handle="",
            public_identity_mode="display_name",
            default_interaction_channel="app_only",
            connect_to_database=lambda **_: _FakeConnection([(1,), (1,), (5, 4, 2, "newsletters")]),
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
            email_communication_preference="no_email",
            public_display_name="",
            public_handle="",
            public_identity_mode="anonymous",
            default_interaction_channel="app_only",
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
            email_communication_preference="newsletters",
            public_display_name="Stephen Trader",
            public_handle="",
            public_identity_mode="display_name",
            default_interaction_channel="app_only",
            connect_to_database=lambda **_: _FakeConnection([(1,), (1,), (5, 4, 2, "newsletters")]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_ACCOUNT_TIMEZONE_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid timezone to raise a stable runtime error.")


def test_raises_clear_error_for_too_many_sidebar_clock_timezones() -> None:
    try:
        save_authenticated_dcx_user_account_editable_settings_capability(
            authenticated_user_id=5,
            preferred_language_id=4,
            preferred_timezone_id=2,
            email_communication_preference="newsletters",
            public_display_name="Stephen Trader",
            public_handle="",
            public_identity_mode="display_name",
            default_interaction_channel="app_only",
            sidebar_clock_timezone_ids=[1, 2, 3],
            connect_to_database=lambda **_: _FakeConnection([(1,), (1,), (5, 4, 2, "newsletters")]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_ACCOUNT_TIMEZONE_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid sidebar clock timezone selection to raise a stable runtime error.")


def test_raises_clear_error_for_invalid_trade_interest_material_key() -> None:
    try:
        save_authenticated_dcx_user_account_editable_settings_capability(
            authenticated_user_id=5,
            preferred_language_id=None,
            preferred_timezone_id=None,
            email_communication_preference="newsletters",
            public_display_name="Stephen Trader",
            public_handle="",
            public_identity_mode="display_name",
            default_interaction_channel="app_only",
            trade_interest_material_keys=["not_a_material"],
            connect_to_database=lambda **_: _FakeConnection(
                [
                    None,
                    (5, None, None, "newsletters", "Stephen Trader", "", "display_name", "app_only"),
                ],
                [[]],
            ),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_ACCOUNT_TRADE_INTERESTS_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid trade interest material to raise a stable runtime error.")
