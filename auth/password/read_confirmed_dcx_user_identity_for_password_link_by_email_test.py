from auth.password.read_confirmed_dcx_user_identity_for_password_link_by_email import (
    read_confirmed_dcx_user_identity_for_password_link_by_email,
)


class _FakeCursor:
    def __init__(self, fetchone_result):
        self._fetchone_result = fetchone_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchone(self):
        return self._fetchone_result


class _FakeConnection:
    def __init__(self, fetchone_result):
        self._cursor = _FakeCursor(fetchone_result)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


def test_returns_confirmed_user_identity_payload_for_verified_login_enabled_email_contact_method() -> None:
    payload = read_confirmed_dcx_user_identity_for_password_link_by_email(
        normalized_email="lookup@example.com",
        connect_to_database=lambda **_: _FakeConnection(
            (
                91,
                "lookup@example.com",
                191,
                "en",
            )
        ),
    )

    assert payload == {
        "user_id": 91,
        "delivery_email": "lookup@example.com",
        "user_auth_identity_id": 191,
        "language_code": "en",
    }


def test_returns_none_for_unconfirmed_user() -> None:
    assert (
        read_confirmed_dcx_user_identity_for_password_link_by_email(
            normalized_email="unconfirmed@example.com",
            connect_to_database=lambda **_: _FakeConnection(None),
        )
        is None
    )
