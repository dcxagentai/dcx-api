"""
CONTEXT:
This file verifies the bootstrap test schema apply capability next to the implementation so the
schema-apply contract stays locally visible and executable.
"""

from dcx_storage.dcx_apply_bootstrap_test_schema_to_configured_database import (
    apply_bootstrap_test_schema_to_configured_database,
)


class FakeCursor:
    def __init__(self):
        self.executed_sql = None

    def execute(self, sql: str) -> None:
        self.executed_sql = sql

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_executes_schema_sql_against_configured_connection() -> None:
    fake_connection = FakeConnection()

    apply_bootstrap_test_schema_to_configured_database(
        connect_to_database=lambda **_: fake_connection,
    )

    assert "CREATE TABLE IF NOT EXISTS dcx_bootstrap_test_messages" in fake_connection.cursor_instance.executed_sql
    assert "INSERT INTO dcx_bootstrap_test_messages" in fake_connection.cursor_instance.executed_sql


def test_returns_applied_status_payload_when_execution_succeeds() -> None:
    payload = apply_bootstrap_test_schema_to_configured_database(
        connect_to_database=lambda **_: FakeConnection(),
    )

    assert payload["status"] == "applied"
    assert payload["applied_sql_file"] == "dcx_bootstrap_test_schema_2026_03_17.sql"
