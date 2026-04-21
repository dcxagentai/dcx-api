from admin.users.read_dcx_admin_user_list import read_dcx_admin_user_list_capability


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


def test_returns_user_rows_with_preferred_language_details() -> None:
    result = read_dcx_admin_user_list_capability(
        connect_to_database=lambda **_: _FakeConnection(
            [
                (
                    1,
                    "caa94290-93cc-4fea-89ac-a4db936d5c8b",
                    "matbenet77@gmail.com",
                    True,
                    1775324331389,
                    "+34647818143",
                    True,
                    1775325300000,
                    "dev",
                    "confirmed",
                    "newsletters",
                    1775324331389,
                    1773936459277,
                    1775324331563,
                    4,
                    "de",
                    "German",
                    "Deutsch",
                    False,
                ),
                (
                    6,
                    "57fd3e38-e777-4356-9dac-226d6d97495f",
                    "jill.whitney@ncmedia.ch",
                    True,
                    1774346486995,
                    "+41440000000",
                    False,
                    None,
                    "user",
                    "confirmed",
                    "newsletters",
                    1774346486995,
                    1774346415341,
                    1774346487162,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            ]
        ),
    )

    assert result["total_user_count"] == 2
    assert result["users"][0]["preferred_language"]["language_code"] == "de"
    assert result["users"][0]["user_role"] == "dev"
    assert result["users"][0]["primary_phone_confirmed"] is True
    assert result["users"][1]["user_role"] == "user"
    assert result["users"][1]["primary_phone_confirmed"] is False
    assert result["users"][1]["preferred_language"] is None


def test_returns_empty_list_when_no_users_exist() -> None:
    result = read_dcx_admin_user_list_capability(
        connect_to_database=lambda **_: _FakeConnection([]),
    )

    assert result == {
        "users": [],
        "total_user_count": 0,
    }
