from starlette.requests import Request

import auth.session.read_authenticated_dcx_session_from_request as session_read_module


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


def _build_request_with_cookie(cookie_header: str | None) -> Request:
    headers = []
    if cookie_header is not None:
        headers.append((b"cookie", cookie_header.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/auth/session",
            "headers": headers,
        }
    )


def test_returns_none_when_cookie_missing() -> None:
    request = _build_request_with_cookie(None)

    assert session_read_module.read_authenticated_dcx_session_from_request(
        request=request,
        connect_to_database=lambda **_: _FakeConnection(None),
    ) is None


def test_returns_session_payload_when_active_cookie_matches_database_row() -> None:
    request = _build_request_with_cookie("dcx_session=raw-token")

    result = session_read_module.read_authenticated_dcx_session_from_request(
        request=request,
        connect_to_database=lambda **_: _FakeConnection(
            (
                11,
                5,
                1775520000000,
                1776729600000,
                1775520300000,
                "3a22bcc2-9265-4639-aac8-1769ddb989c4",
                "matbenet77@gmail.com",
                "admin",
                "confirmed",
                2,
                "Europe/Madrid",
                "Madrid",
            )
        ),
    )

    assert result == {
        "session_id": 11,
        "user_id": 5,
        "issued_at_ts_ms": 1775520000000,
        "expires_at_ts_ms": 1776729600000,
        "last_seen_at_ts_ms": 1775520300000,
        "user_uuid": "3a22bcc2-9265-4639-aac8-1769ddb989c4",
        "primary_email": "matbenet77@gmail.com",
        "user_role": "admin",
        "account_status": "confirmed",
        "preferred_timezone": {
            "id": 2,
            "iana_name": "Europe/Madrid",
            "display_label": "Madrid",
        },
        "may_access_app": True,
        "may_access_admin": True,
    }
