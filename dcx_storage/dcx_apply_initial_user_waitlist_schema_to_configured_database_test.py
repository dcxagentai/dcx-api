"""
CONTEXT:
This file verifies the first durable DCX user waitlist schema apply capability next to the
implementation so the schema-init contract stays locally visible and executable.
"""

from dcx_storage.dcx_apply_initial_user_waitlist_schema_to_configured_database import (
    apply_initial_user_waitlist_schema_to_configured_database,
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

    apply_initial_user_waitlist_schema_to_configured_database(
        connect_to_database=lambda **_: fake_connection,
    )

    assert "CREATE TABLE IF NOT EXISTS stephen_dcx_languages" in fake_connection.cursor_instance.executed_sql
    assert "CREATE TABLE IF NOT EXISTS stephen_dcx_users" in fake_connection.cursor_instance.executed_sql


def test_returns_applied_status_payload_when_execution_succeeds() -> None:
    payload = apply_initial_user_waitlist_schema_to_configured_database(
        connect_to_database=lambda **_: FakeConnection(),
    )

    assert payload["status"] == "applied"
    assert payload["applied_sql_file"] == "dcx_initial_user_waitlist_schema_2026_03_18.sql"


def test_schema_sql_contains_four_project_prefixed_tables() -> None:
    payload = apply_initial_user_waitlist_schema_to_configured_database(
        connect_to_database=lambda **_: FakeConnection(),
    )

    assert payload["ensured_tables"] == [
        "stephen_dcx_languages",
        "stephen_dcx_users",
        "stephen_dcx_user_auth_identities",
        "stephen_dcx_user_auth_challenges",
    ]


def test_schema_sql_contains_no_seed_inserts() -> None:
    fake_connection = FakeConnection()

    apply_initial_user_waitlist_schema_to_configured_database(
        connect_to_database=lambda **_: fake_connection,
    )

    assert "INSERT INTO" not in fake_connection.cursor_instance.executed_sql
    assert "DELETE FROM" not in fake_connection.cursor_instance.executed_sql
