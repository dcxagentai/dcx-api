"""
CONTEXT:
This file falsifies the Postgres-backed public route rate-limit capability for DCX.
It keeps the per-IP abuse brake executable near the implementation.
"""

from system.rate_limits.enforce_public_route_rate_limit import (
    enforce_public_route_rate_limit_capability,
)


class FakeCursor:
    def __init__(self, fetchone_results):
        self.fetchone_results = list(fetchone_results)
        self.executed_statements = []

    def execute(self, sql, params=None):
        self.executed_statements.append((sql, params))

    def fetchone(self):
        if not self.fetchone_results:
            return None

        return self.fetchone_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, fetchone_results):
        self.cursor_instance = FakeCursor(fetchone_results)

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_first_hit_creates_window_row() -> None:
    fake_connection = FakeConnection(fetchone_results=[(1,)])

    payload = enforce_public_route_rate_limit_capability(
        route_key="users_signup_email",
        client_ip="127.0.0.1",
        max_requests=5,
        window_ms=900000,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1710000000000,
    )

    assert payload["request_count"] == 1
    assert payload["window_started_at_ts_ms"] == 1710000000000


def test_over_budget_hit_raises_rate_limit_error() -> None:
    fake_connection = FakeConnection(fetchone_results=[(6,)])

    try:
        enforce_public_route_rate_limit_capability(
            route_key="users_signup_email",
            client_ip="127.0.0.1",
            max_requests=5,
            window_ms=900000,
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1710000000000,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_EXCEEDED"
    else:
        raise AssertionError("Expected rate-limit error.")
