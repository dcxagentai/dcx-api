"""
CONTEXT:
This file verifies the first real local Postgres read capability used by the DCX API bootstrap shell.
It keeps the capability contract executable next to the implementation file.
"""

from datetime import datetime, timezone

from dcx_api_read_latest_raw_message_from_local_postgres_bootstrap_capability import (
    read_latest_raw_message_from_local_postgres_bootstrap_capability,
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


def test_returns_normalized_latest_message_payload_when_row_exists() -> None:
    fake_row = (
        78,
        "Ok, ótimo negócio.",
        "inbound",
        "whatsapp",
        12,
        34,
        datetime(2026, 3, 3, 13, 47, 40, tzinfo=timezone.utc),
    )

    payload = read_latest_raw_message_from_local_postgres_bootstrap_capability(
        connect_to_database=lambda **_: FakeConnection(fake_row),
    )

    assert payload["status"] == "ready"
    assert payload["message_id"] == 78
    assert payload["preview_text"] == "Ok, ótimo negócio."
    assert payload["message_direction"] == "inbound"
    assert payload["channel_type"] == "whatsapp"


def test_returns_empty_state_payload_when_no_rows_exist() -> None:
    payload = read_latest_raw_message_from_local_postgres_bootstrap_capability(
        connect_to_database=lambda **_: FakeConnection(None),
    )

    assert payload["status"] == "empty"
    assert payload["message_id"] is None
    assert payload["preview_text"] == "No raw messages found in local Postgres."


def test_converts_received_at_to_iso8601_string() -> None:
    fake_row = (
        1,
        "hello",
        "inbound",
        "whatsapp",
        None,
        None,
        datetime(2026, 3, 3, 13, 47, 40, tzinfo=timezone.utc),
    )

    payload = read_latest_raw_message_from_local_postgres_bootstrap_capability(
        connect_to_database=lambda **_: FakeConnection(fake_row),
    )

    assert payload["received_at"] == "2026-03-03T13:47:40+00:00"
