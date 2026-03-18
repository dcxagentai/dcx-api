"""
CONTEXT:
This file applies the first durable DCX user waitlist schema to the currently configured Postgres
database. It exists so local development and Render production can both ensure the same four-table
foundation is present before the first real email-signup user flow is implemented.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import psycopg2

from dcx_storage.db_config import DB_CONFIG


def apply_initial_user_waitlist_schema_to_configured_database(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured Postgres database is reachable with the current db_config values.
        - The initial user waitlist schema SQL file exists on disk next to this capability.
      postconditions:
        - The first four stephen_dcx user waitlist tables exist in the configured database.
        - The helper trigger function for updated_at_ts_ms exists.
        - No seed data is inserted and no existing rows are deleted.
      side_effects:
        - executes one schema SQL file against the configured database
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_initial_user_waitlist_schema_apply_v1
      locks: []
      contention_strategy: rely on IF NOT EXISTS, UNIQUE constraints, and CREATE OR REPLACE FUNCTION to keep repeated applies safe

    NARRATIVE:
      why:
        - This exists to replace the one-table bootstrap proof with the first real user-domain schema foundation for the DCX MVP.
        - The first public product milestone needs durable tables for users, auth identities, auth challenges, and languages before API routes are added.
      when_to_use:
        - At backend startup so fresh local or production databases can self-initialize safely.
        - Before implementing the first email-signup waitlist capability.
      when_not_to_use:
        - Do not use this to seed demo content or test rows.
        - Do not use this as the only migration strategy once the schema starts evolving beyond the initial four tables.
      what_can_go_wrong:
        - The configured database may not be reachable.
        - The SQL file may be missing or moved.
        - The database user may lack create-table or create-trigger permissions.
      what_comes_next:
        - Implement the first users/auth challenge capabilities on top of these tables.
        - Add explicit non-breaking migration files when the initial schema changes later.

    TESTS:
      - executes_schema_sql_against_configured_connection
      - returns_applied_status_payload_when_execution_succeeds
      - schema_sql_contains_four_project_prefixed_tables
      - schema_sql_contains_no_seed_inserts

    ERRORS:
      - API_INITIAL_USER_WAITLIST_SCHEMA_APPLY_FAILED:
          suggested_action: Confirm the configured Postgres database is reachable and the initial schema SQL file is present.
          common_causes:
            - database credentials wrong
            - database service stopped
            - SQL file path moved or deleted
            - database user lacks schema write permissions
          recovery_steps:
            - Re-check dcx_storage.db_config.py values.
            - Confirm the SQL file exists next to this script.
            - Retry after verifying database connectivity and permissions.
          retry_safe: true
          what_changed: unknown until transaction outcome is inspected
          rollback_needed: false
          rollback_operation: inspect manually only if a partial external schema change occurred

    CODE:
    """
    connect = connect_to_database or psycopg2.connect
    schema_sql = _read_initial_user_waitlist_schema_sql()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(schema_sql)
    except Exception as exc:  # pragma: no cover - exercised through integration usage
        raise RuntimeError("API_INITIAL_USER_WAITLIST_SCHEMA_APPLY_FAILED") from exc

    return {
        "status": "applied",
        "applied_sql_file": "dcx_initial_user_waitlist_schema_2026_03_18.sql",
        "ensured_tables": [
            "stephen_dcx_languages",
            "stephen_dcx_users",
            "stephen_dcx_user_auth_identities",
            "stephen_dcx_user_auth_challenges",
        ],
    }


def _read_initial_user_waitlist_schema_sql() -> str:
    """Minimal contract: load the initial user waitlist schema SQL text from the colocated schema file."""
    schema_path = Path(__file__).with_name("dcx_initial_user_waitlist_schema_2026_03_18.sql")
    return schema_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    result = apply_initial_user_waitlist_schema_to_configured_database()
    print(f"Applied: {result['applied_sql_file']} ({result['status']})")
