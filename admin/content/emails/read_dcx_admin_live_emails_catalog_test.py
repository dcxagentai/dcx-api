from admin.content.emails.read_dcx_admin_live_emails_catalog import (
    read_dcx_admin_live_emails_catalog_capability,
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


def test_returns_live_email_rows_with_language_details() -> None:
    result = read_dcx_admin_live_emails_catalog_capability(
        connect_to_database=lambda **_: _FakeConnection(
            [
                (
                    1,
                    "transactional",
                    "signup_verify_otp",
                    "DCX Agentic: Your verification code",
                    "Your DCX Agentic verification code is:\n\n{{ otp_code }}",
                    True,
                    True,
                    None,
                    None,
                    1775319000000,
                    1775319000100,
                    1,
                    "en",
                    "English",
                    "English",
                    False,
                ),
                (
                    2,
                    "transactional",
                    "signup_verify_otp",
                    "DCX Agentic : Votre code de vérification",
                    "Votre code de vérification DCX Agentic est :\n\n{{ otp_code }}",
                    False,
                    True,
                    None,
                    1,
                    1775319000200,
                    1775319000300,
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
    assert result["emails"][0]["email_type"] == "transactional"
    assert result["emails"][1]["language"]["language_code"] == "fr"


def test_returns_empty_catalog_when_no_live_emails_exist() -> None:
    result = read_dcx_admin_live_emails_catalog_capability(
        connect_to_database=lambda **_: _FakeConnection([]),
    )

    assert result == {
        "emails": [],
        "total_live_row_count": 0,
    }
