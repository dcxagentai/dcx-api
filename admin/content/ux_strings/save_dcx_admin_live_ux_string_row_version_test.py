from admin.content.ux_strings.save_dcx_admin_live_ux_string_row_version import (
    save_dcx_admin_live_ux_string_row_version_capability,
)


class _FakeCursor:
    def __init__(self, fetchone_results):
        self._fetchone_results = list(fetchone_results)
        self.executed_queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
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


def test_inserts_new_live_version_when_text_changes() -> None:
    result = save_dcx_admin_live_ux_string_row_version_capability(
        target_ux_string_id=101,
        next_text="Updated translated value",
        connect_to_database=lambda **_: _FakeConnection(
            [
                (101, "signup_otp_form", "restart_message", 2, "Old translated value", False, 55),
                (202,),
            ]
        ),
    )

    assert result == {
        "ux_string_id": 202,
        "previous_ux_string_id": 101,
        "was_noop": False,
    }


def test_returns_noop_when_text_is_unchanged() -> None:
    result = save_dcx_admin_live_ux_string_row_version_capability(
        target_ux_string_id=101,
        next_text="Same value",
        connect_to_database=lambda **_: _FakeConnection(
            [
                (101, "signup_otp_form", "restart_message", 2, "Same value", False, 55),
            ]
        ),
    )

    assert result == {
        "ux_string_id": 101,
        "was_noop": True,
    }


def test_raises_clear_error_for_blank_text() -> None:
    try:
        save_dcx_admin_live_ux_string_row_version_capability(
            target_ux_string_id=101,
            next_text="   ",
            connect_to_database=lambda **_: _FakeConnection([]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_ADMIN_UX_STRING_TEXT_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected blank UX-string text to raise a stable runtime error.")


def test_raises_clear_error_for_missing_live_row() -> None:
    try:
        save_dcx_admin_live_ux_string_row_version_capability(
            target_ux_string_id=101,
            next_text="Updated translated value",
            connect_to_database=lambda **_: _FakeConnection([None]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_ADMIN_UX_STRING_LIVE_ROW_NOT_FOUND"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected missing live UX-string row to raise a stable runtime error.")
