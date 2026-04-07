from auth.session.revoke_all_dcx_auth_sessions_for_user import (
    revoke_all_dcx_auth_sessions_for_user,
)


class _FakeCursor:
    def __init__(self, rowcount):
        self.rowcount = rowcount

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params


class _FakeConnection:
    def __init__(self, rowcount):
        self._cursor = _FakeCursor(rowcount)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


def test_revokes_all_active_sessions_for_user() -> None:
    payload = revoke_all_dcx_auth_sessions_for_user(
        authenticated_user_id=31,
        connect_to_database=lambda **_: _FakeConnection(2),
        current_timestamp_ms_provider=lambda: 1775000000000,
    )

    assert payload["revoked_count"] == 2
