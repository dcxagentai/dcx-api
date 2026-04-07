from unittest.mock import patch

import auth.login.login_dcx_user_with_email_and_password as login_module


class _FakeCursor:
    def __init__(self, fetchone_result):
        self._fetchone_result = fetchone_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchone(self):
        return self._fetchone_result


class _FakeConnection:
    def __init__(self, fetchone_result):
        self._fetchone_result = fetchone_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._fetchone_result)


def test_login_returns_session_payload_for_valid_email_and_password() -> None:
    with patch.object(login_module, "verify_dcx_password_hash", return_value=True), patch.object(
        login_module,
        "create_dcx_auth_session",
        return_value={
            "session_id": 301,
            "raw_session_token": "raw-token",
            "expires_at_ts_ms": 1778000000000,
        },
    ):
        result = login_module.login_dcx_user_with_email_and_password(
            email="MatBenet77@gmail.com",
            candidate_password="correct horse battery staple",
            request_ip="127.0.0.1",
            request_user_agent="pytest",
            connect_to_database=lambda **_: _FakeConnection(
                (
                    5,
                    "3a22bcc2-9265-4639-aac8-1769ddb989c4",
                    "matbenet77@gmail.com",
                    "admin",
                    "confirmed",
                    True,
                    "$argon2id$fake",
                )
            ),
        )

    assert result["session_id"] == 301
    assert result["raw_session_token"] == "raw-token"
    assert result["user"]["allowed_surfaces"]["admin"] is True


def test_login_raises_invalid_credentials_for_wrong_password() -> None:
    with patch.object(login_module, "verify_dcx_password_hash", return_value=False):
        try:
            login_module.login_dcx_user_with_email_and_password(
                email="matbenet77@gmail.com",
                candidate_password="wrong",
                request_ip="127.0.0.1",
                request_user_agent="pytest",
                connect_to_database=lambda **_: _FakeConnection(
                    (
                        5,
                        "3a22bcc2-9265-4639-aac8-1769ddb989c4",
                        "matbenet77@gmail.com",
                        "user",
                        "confirmed",
                        True,
                        "$argon2id$fake",
                    )
                ),
            )
        except RuntimeError as exc:
            assert str(exc) == "API_DCX_AUTH_LOGIN_INVALID_CREDENTIALS"
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected invalid credentials to raise a stable runtime error.")


def test_login_raises_invalid_credentials_when_password_not_set() -> None:
    try:
        login_module.login_dcx_user_with_email_and_password(
            email="matbenet77@gmail.com",
            candidate_password="wrong",
            request_ip="127.0.0.1",
            request_user_agent="pytest",
            connect_to_database=lambda **_: _FakeConnection(
                (
                    5,
                    "3a22bcc2-9265-4639-aac8-1769ddb989c4",
                    "matbenet77@gmail.com",
                    "user",
                    "confirmed",
                    True,
                    None,
                )
            ),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_AUTH_LOGIN_INVALID_CREDENTIALS"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected password-not-set login to raise a stable runtime error.")
