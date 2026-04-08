from languages.read_live_dcx_ux_string_group_with_language_fallback import (
    read_live_dcx_ux_string_group_with_language_fallback_capability,
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
    result = read_live_dcx_ux_string_group_with_language_fallback_capability(
        string_group="app_auth_login_page",
        language_code="fr",
        default_ux_strings={"page_title": "Sign in"},
        connect_to_database=lambda **_: _FakeConnection([]),
    )

    assert result == {"page_title": "Sign in"}


def test_overlays_requested_language_rows_on_top_of_original_rows() -> None:
    result = read_live_dcx_ux_string_group_with_language_fallback_capability(
        string_group="app_auth_login_page",
        language_code="fr",
        default_ux_strings={
            "page_title": "Sign in",
            "headline": "Continue into the private DCX app.",
        },
        connect_to_database=lambda **_: _FakeConnection(
            [
                ("page_title", "Sign in", True, "en"),
                ("page_title", "Connexion", False, "fr"),
                ("headline", "Continue into the private DCX app.", True, "en"),
            ]
        ),
    )

    assert result["page_title"] == "Connexion"
    assert result["headline"] == "Continue into the private DCX app."


def test_ignores_unknown_string_keys_not_present_in_defaults() -> None:
    result = read_live_dcx_ux_string_group_with_language_fallback_capability(
        string_group="app_auth_login_page",
        language_code="de",
        default_ux_strings={"page_title": "Sign in"},
        connect_to_database=lambda **_: _FakeConnection(
            [
                ("page_title", "Anmelden", False, "de"),
                ("nonexistent_key", "Should not appear", False, "de"),
            ]
        ),
    )

    assert result == {"page_title": "Anmelden"}
