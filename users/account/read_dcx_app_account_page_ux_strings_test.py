from users.account.read_dcx_app_account_page_ux_strings import (
    DCX_APP_ACCOUNT_PAGE_DEFAULT_UX_STRINGS,
    read_dcx_app_account_page_ux_strings_capability,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._rows)


def test_returns_defaults_when_group_has_not_been_seeded() -> None:
    result = read_dcx_app_account_page_ux_strings_capability(
        preferred_language_code="en",
        connect_to_database=lambda **_: _FakeConnection([]),
    )

    assert result == DCX_APP_ACCOUNT_PAGE_DEFAULT_UX_STRINGS


def test_overlays_selected_language_rows_on_top_of_original_rows() -> None:
    result = read_dcx_app_account_page_ux_strings_capability(
        preferred_language_code="es",
        connect_to_database=lambda **_: _FakeConnection(
            [
                ("page_title", "Account", True, "en"),
                ("page_title", "Cuenta", False, "es"),
                ("field_primary_email", "Primary email", True, "en"),
                ("field_primary_phone", "Primary phone", True, "en"),
            ]
        ),
    )

    assert result["page_title"] == "Cuenta"
    assert result["field_primary_email"] == "Primary email"
    assert result["field_primary_phone"] == "Primary phone"
