from admin.content.ux_strings.read_dcx_admin_live_ux_strings_catalog import (
    read_dcx_admin_live_ux_strings_catalog_capability,
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


def test_returns_live_ux_string_rows_with_language_details() -> None:
    result = read_dcx_admin_live_ux_strings_catalog_capability(
        connect_to_database=lambda **_: _FakeConnection(
            [
                (
                    101,
                    "signup_otp_form",
                    "restart_message",
                    "This verification session has expired.",
                    True,
                    True,
                    None,
                    None,
                    1775318000000,
                    1775318000100,
                    1,
                    "en",
                    "English",
                    "English",
                    False,
                ),
                (
                    102,
                    "signup_otp_form",
                    "restart_message",
                    "Cette session de vérification a expiré.",
                    False,
                    True,
                    None,
                    101,
                    1775318000200,
                    1775318000300,
                    3,
                    "fr",
                    "French",
                    "Français",
                    False,
                ),
            ]
        ),
    )

    assert result["total_live_row_count"] == 2
    assert result["ux_strings"][0]["string_group"] == "signup_otp_form"
    assert result["ux_strings"][1]["language"]["language_code"] == "fr"


def test_returns_empty_catalog_when_no_live_ux_strings_exist() -> None:
    result = read_dcx_admin_live_ux_strings_catalog_capability(
        connect_to_database=lambda **_: _FakeConnection([]),
    )

    assert result == {
        "ux_strings": [],
        "total_live_row_count": 0,
    }
