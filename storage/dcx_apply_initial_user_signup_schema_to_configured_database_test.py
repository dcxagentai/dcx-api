"""
CONTEXT:
This file verifies the durable DCX user-signup schema apply capability next to the
implementation so the startup schema-init contract stays executable.
"""

from storage.dcx_apply_initial_user_signup_schema_to_configured_database import (
    apply_initial_user_signup_schema_to_configured_database,
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

    apply_initial_user_signup_schema_to_configured_database(
        connect_to_database=lambda **_: fake_connection,
    )

    assert "CREATE TABLE IF NOT EXISTS stephen_dcx_languages" in fake_connection.cursor_instance.executed_sql
    assert "ALTER TABLE stephen_dcx_user_auth_challenges" in fake_connection.cursor_instance.executed_sql


def test_returns_applied_status_payload_when_execution_succeeds() -> None:
    payload = apply_initial_user_signup_schema_to_configured_database(
        connect_to_database=lambda **_: FakeConnection(),
    )

    assert payload["status"] == "applied"
    assert payload["applied_sql_file"] == "dcx_initial_user_signup_schema_2026_03_18.sql"


def test_schema_sql_contains_signup_challenge_hardening_columns() -> None:
    payload = apply_initial_user_signup_schema_to_configured_database(
        connect_to_database=lambda **_: FakeConnection(),
    )

    assert payload["ensured_tables"] == [
        "stephen_dcx_languages",
        "stephen_dcx_users",
        "stephen_dcx_user_auth_identities",
        "stephen_dcx_user_auth_challenges",
        "stephen_dcx_public_route_rate_limits",
    ]


def test_schema_sql_contains_rate_limit_table() -> None:
    fake_connection = FakeConnection()

    apply_initial_user_signup_schema_to_configured_database(
        connect_to_database=lambda **_: fake_connection,
    )

    assert "CREATE TABLE IF NOT EXISTS stephen_dcx_public_route_rate_limits" in fake_connection.cursor_instance.executed_sql
