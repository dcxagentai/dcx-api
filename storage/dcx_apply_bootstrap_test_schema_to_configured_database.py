"""
CONTEXT:
This file applies the fresh minimal bootstrap test schema to the currently configured DCX Postgres
database. It exists so the local backend and the later production backend can both be pointed at
the same tiny one-table schema proof before the real MVP schema is redesigned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def apply_bootstrap_test_schema_to_configured_database(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured Postgres database is reachable with the current db_config values.
        - The bootstrap schema SQL file exists on disk next to this capability.
      postconditions:
        - The dcx_bootstrap_test_messages table exists in the configured database.
        - One stable bootstrap test message row exists or is refreshed.
      side_effects:
        - executes one schema SQL file against the configured database
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_bootstrap_test_schema_apply_v1
      locks: []
      contention_strategy: rely on IF NOT EXISTS and ON CONFLICT to make repeated applies safe

    NARRATIVE:
      why: This exists to create the smallest possible fresh schema proof for the DCX local-to-production plumbing path.
      when_to_use:
        - Before testing the backend against the new bootstrap test table.
        - Before pointing a fresh local or production database at the DCX MVP shell.
      when_not_to_use:
        - Do not use this as the long-term schema migration strategy for the real MVP database.
        - Do not use this to recreate the older alpha schema.
      what_can_go_wrong:
        - The configured database may not be reachable.
        - The SQL file may be missing or moved.
        - The database user may lack schema write permissions.
      what_comes_next:
        - Read the seeded test message through the backend bootstrap route.
        - Later replace this with a proper migration sequence for the real MVP schema.

    TESTS:
      - executes_schema_sql_against_configured_connection
      - returns_applied_status_payload_when_execution_succeeds

    ERRORS:
      - API_BOOTSTRAP_TEST_SCHEMA_APPLY_FAILED:
          suggested_action: Confirm the configured Postgres database is reachable and the SQL file is present.
          common_causes:
            - database credentials wrong
            - database service stopped
            - SQL file path moved or deleted
            - database user lacks create-table privileges
          recovery_steps:
            - Re-check dcx_storage.db_config.py values.
            - Confirm the SQL file exists next to this script.
            - Retry after verifying database connectivity and permissions.
          retry_safe: true
          what_changed: unknown until transaction outcome is inspected
          rollback_needed: false
          rollback_operation: rerun against a clean database only if a partial manual rollback is required

    CODE:
    """
    connect = connect_to_database or psycopg2.connect
    schema_sql = _read_bootstrap_test_schema_sql()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(schema_sql)
    except Exception as exc:  # pragma: no cover - exercised through integration usage
        raise RuntimeError("API_BOOTSTRAP_TEST_SCHEMA_APPLY_FAILED") from exc

    return {
        "status": "applied",
        "applied_sql_file": "dcx_bootstrap_test_schema_2026_03_17.sql",
    }


def _read_bootstrap_test_schema_sql() -> str:
    """Minimal contract: load the bootstrap schema SQL text from the colocated schema file."""
    schema_path = Path(__file__).with_name("dcx_bootstrap_test_schema_2026_03_17.sql")
    return schema_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    result = apply_bootstrap_test_schema_to_configured_database()
    print(f"Applied: {result['applied_sql_file']} ({result['status']})")
