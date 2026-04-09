"""
CONTEXT:
This file applies the durable DCX user-signup schema to the configured Postgres database.
It exists so local and production startup can ensure the evolving signup/auth challenge
tables and non-breaking hardening additions are present without deleting existing data.
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def apply_initial_user_signup_schema_to_configured_database(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured Postgres database is reachable.
        - The colocated schema SQL file exists.
      postconditions:
        - The DCX user-signup schema and non-breaking hardening additions exist in the configured database.
        - No seed rows are inserted and no existing rows are deleted.
      side_effects:
        - executes one schema SQL file against the configured database
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_initial_user_signup_schema_apply_v2
      locks: []
      contention_strategy: rely on CREATE IF NOT EXISTS, ALTER TABLE ADD COLUMN IF NOT EXISTS, and idempotent updates to keep repeated applies safe

    NARRATIVE:
      WHY this exists:
        - The public email-signup flow now needs a durable migration path for new challenge and rate-limit fields without destructive resets.
      WHEN TO USE it:
        - Use it at backend startup.
      WHEN NOT TO USE it:
        - Do not use it for seed data or destructive resets.
      WHAT CAN GO WRONG:
        - DB connectivity or permissions can fail.
      WHAT COMES NEXT:
        - Explicit migration tooling can replace this startup apply path once the schema evolves further.

    TESTS:
      - executes_schema_sql_against_configured_connection
      - returns_applied_status_payload_when_execution_succeeds
      - schema_sql_contains_signup_challenge_hardening_columns
      - schema_sql_contains_rate_limit_table

    ERRORS:
      - API_INITIAL_USER_SIGNUP_SCHEMA_APPLY_FAILED:
          suggested_action: Confirm database connectivity and schema-write permissions.
          common_causes:
            - wrong db credentials
            - missing SQL file
            - insufficient permissions
          recovery_steps:
            - Re-check DB config.
            - Confirm the schema SQL file exists.
            - Retry once the database is reachable and writable.
          retry_safe: true
          what_changed: unknown until the transaction outcome is inspected
          rollback_needed: false
          rollback_operation: inspect manually only if a partial external schema change occurred

    CODE:
    """
    connect = connect_to_database or psycopg2.connect
    schema_sql = _read_initial_user_signup_schema_sql()

    last_error: Exception | None = None

    for attempt_number in range(1, 5):
        try:
            with connect(**DB_CONFIG) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(schema_sql)
            last_error = None
            break
        except psycopg2.OperationalError as exc:  # pragma: no cover - integration path
            last_error = exc
            if attempt_number >= 4:
                break
            time.sleep(min(attempt_number * 2, 6))
        except Exception as exc:  # pragma: no cover - integration path
            raise RuntimeError("API_INITIAL_USER_SIGNUP_SCHEMA_APPLY_FAILED") from exc

    if last_error is not None:  # pragma: no cover - integration path
        raise RuntimeError("API_INITIAL_USER_SIGNUP_SCHEMA_APPLY_FAILED") from last_error

    return {
        "status": "applied",
        "applied_sql_file": "dcx_initial_user_signup_schema_2026_03_18.sql",
        "ensured_tables": [
            "stephen_dcx_languages",
            "stephen_dcx_users",
            "stephen_dcx_user_auth_identities",
            "stephen_dcx_user_auth_challenges",
            "stephen_dcx_user_password_credentials",
            "stephen_dcx_user_auth_sessions",
            "stephen_dcx_public_route_rate_limits",
        ],
    }


def _read_initial_user_signup_schema_sql() -> str:
    """Minimal contract: load the colocated user-signup schema SQL text from disk."""
    schema_path = Path(__file__).with_name("dcx_initial_user_signup_schema_2026_03_18.sql")
    return schema_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    result = apply_initial_user_signup_schema_to_configured_database()
    print(f"Applied: {result['applied_sql_file']} ({result['status']})")
