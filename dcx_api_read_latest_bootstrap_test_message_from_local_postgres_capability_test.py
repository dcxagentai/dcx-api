"""
CONTEXT:
This file verifies the fresh bootstrap test message read capability used by the DCX API shell after
the alpha schema was set aside.
"""

from datetime import datetime, timezone

from dcx_api_read_latest_bootstrap_test_message_from_local_postgres_capability import (
    read_latest_bootstrap_test_message_from_local_postgres_capability,
)


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.executed_sql = None

    def execute(self, sql: str) -> None:
        self.executed_sql = sql

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, row):
        self.row = row

    def cursor(self):
        return FakeCursor(self.row)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_returns_normalized_latest_bootstrap_message_payload_when_row_exists() -> None:
    fake_row = (
        1,
        "Hello from the fresh DCX bootstrap test schema.",
        "system",
        "bootstrap",
        datetime(2026, 3, 17, 18, 30, 0, tzinfo=timezone.utc),
    )

    payload = read_latest_bootstrap_test_message_from_local_postgres_capability(
        connect_to_database=lambda **_: FakeConnection(fake_row),
    )

    assert payload["status"] == "ready"
    assert payload["message_id"] == 1
    assert payload["preview_text"] == "Hello from the fresh DCX bootstrap test schema."
    assert payload["message_direction"] == "system"
    assert payload["channel_type"] == "bootstrap"


def test_returns_empty_state_payload_when_no_rows_exist() -> None:
    payload = read_latest_bootstrap_test_message_from_local_postgres_capability(
        connect_to_database=lambda **_: FakeConnection(None),
    )

    assert payload["status"] == "empty"
    assert payload["message_id"] is None
    assert payload["preview_text"] == "No bootstrap test messages found in local Postgres."


def test_converts_created_at_to_iso8601_string() -> None:
    fake_row = (
        1,
        "hello",
        "system",
        "bootstrap",
        datetime(2026, 3, 17, 18, 30, 0, tzinfo=timezone.utc),
    )

    payload = read_latest_bootstrap_test_message_from_local_postgres_capability(
        connect_to_database=lambda **_: FakeConnection(fake_row),
    )

    assert payload["received_at"] == "2026-03-17T18:30:00+00:00"
