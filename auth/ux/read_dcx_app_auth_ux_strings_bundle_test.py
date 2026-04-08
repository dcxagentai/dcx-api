from auth.ux.read_dcx_app_auth_ux_strings_bundle import (
    read_dcx_app_auth_ux_strings_bundle_capability,
)


def test_returns_bundle_with_selected_language_rows_when_present() -> None:
    rows_by_group = {
        "app_auth_common": [("checking_session", "Verification de session...", False, "fr")],
        "app_auth_login_page": [("page_title", "Connexion", False, "fr")],
        "app_auth_password_reset_request_page": [("page_title", "Reinitialiser le mot de passe", False, "fr")],
        "app_auth_password_set_page": [("page_title", "Mot de passe", False, "fr")],
    }

    result = read_dcx_app_auth_ux_strings_bundle_capability(
        language_code="fr",
        connect_to_database=lambda **_: _FakeConnection(rows_by_group),
    )

    assert result["language_code"] == "fr"
    assert result["common"]["checking_session"] == "Verification de session..."
    assert result["login_page"]["page_title"] == "Connexion"
    assert result["password_reset_request_page"]["page_title"] == "Reinitialiser le mot de passe"
    assert result["password_set_page"]["page_title"] == "Mot de passe"


def test_falls_back_to_defaults_when_groups_are_missing() -> None:
    result = read_dcx_app_auth_ux_strings_bundle_capability(
        language_code=None,
        connect_to_database=lambda **_: _FakeConnection({}),
    )

    assert result["language_code"] == "en"
    assert result["login_page"]["page_title"] == "Sign in"
    assert result["password_reset_request_page"]["page_title"] == "Reset password"
    assert result["password_set_page"]["page_title"] == "Password"


class _FakeCursor:
    def __init__(self, rows_by_group):
        self._rows_by_group = rows_by_group
        self._current_rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        string_group = params[0]
        self._current_rows = self._rows_by_group.get(string_group, [])

    def fetchall(self):
        return self._current_rows


class _FakeConnection:
    def __init__(self, rows_by_group):
        self._rows_by_group = rows_by_group

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._rows_by_group)
