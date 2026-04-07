import auth.session.create_dcx_auth_session as create_session_module


class _FakeCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params):
        self.executed.append((query, params))

    def fetchone(self):
        return (901,)


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor()


def test_creates_session_row_and_returns_raw_token_metadata() -> None:
    result = create_session_module.create_dcx_auth_session(
        authenticated_user_id=5,
        created_from_ip="127.0.0.1",
        created_from_user_agent="pytest",
        connect_to_database=lambda **_: _FakeConnection(),
    )

    assert result["session_id"] == 901
    assert result["raw_session_token"]
    assert result["session_token_hash"]
    assert result["expires_at_ts_ms"] > result["issued_at_ts_ms"]
