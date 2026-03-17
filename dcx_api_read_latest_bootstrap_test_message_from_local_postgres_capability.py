"""
CONTEXT:
This file reads the latest message from the fresh one-table bootstrap schema used for the DCX MVP
plumbing proof. It replaces the earlier dependency on the larger alpha raw-messages table while
keeping the frontend-facing bootstrap payload shape stable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import psycopg2

from dcx_storage.db_config import DB_CONFIG


def read_latest_bootstrap_test_message_from_local_postgres_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The local stephen_dcx Postgres database is reachable with the configured credentials.
        - The dcx_bootstrap_test_messages table exists in the current local schema.
      postconditions:
        - Returns a normalized description of the latest bootstrap test message row.
        - Returns a stable empty-state payload when no bootstrap test rows exist.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why: This exists to prove the local-to-production plumbing against a fresh minimal schema rather than the older alpha tables.
      when_to_use:
        - During bootstrap verification of the DCX MVP shell.
        - When a one-table seeded database read is enough to prove frontend/backend/database connectivity.
      when_not_to_use:
        - Do not use this as the long-term domain query shape for real messages.
        - Do not use this capability for permissions-sensitive or user-scoped reads.
      what_can_go_wrong:
        - The bootstrap test table may not exist yet.
        - The local Postgres instance may be unavailable.
        - The seeded row may have been deleted manually.
      what_comes_next:
        - Replace this with real MVP domain routes once the new schema is designed.
        - Retire the bootstrap test table after plumbing is proven in production.

    TESTS:
      - returns_normalized_latest_bootstrap_message_payload_when_row_exists
      - returns_empty_state_payload_when_no_rows_exist
      - converts_created_at_to_iso8601_string

    ERRORS:
      - API_BOOTSTRAP_TEST_MESSAGE_LOCAL_POSTGRES_UNAVAILABLE:
          suggested_action: Confirm local Postgres is running and the bootstrap test schema was applied successfully.
          common_causes:
            - local Postgres service stopped
            - wrong credentials in db_config
            - bootstrap test schema not applied yet
          recovery_steps:
            - Start local Postgres.
            - Re-check dcx_storage.db_config.py values.
            - Run the bootstrap test schema apply script and retry.
          retry_safe: true

    CODE:
    """
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        text_content,
                        message_direction,
                        channel_type,
                        created_at
                    FROM dcx_bootstrap_test_messages
                    ORDER BY created_at DESC NULLS LAST, id DESC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
    except Exception as exc:  # pragma: no cover - exercised through route tests
        raise RuntimeError("API_BOOTSTRAP_TEST_MESSAGE_LOCAL_POSTGRES_UNAVAILABLE") from exc

    if row is None:
        return {
            "status": "empty",
            "preview_text": "No bootstrap test messages found in local Postgres.",
            "message_id": None,
            "message_direction": None,
            "channel_type": None,
            "sender_user_id": None,
            "receiver_user_id": None,
            "received_at": None,
        }

    (
        message_id,
        text_content,
        message_direction,
        channel_type,
        created_at,
    ) = row

    return {
        "status": "ready",
        "preview_text": text_content,
        "message_id": message_id,
        "message_direction": message_direction,
        "channel_type": channel_type,
        "sender_user_id": None,
        "receiver_user_id": None,
        "received_at": _normalize_timestamp_to_iso8601_string(created_at),
    }


def _normalize_timestamp_to_iso8601_string(timestamp_value: datetime | None) -> str | None:
    """Minimal contract: convert datetime values into stable ISO-8601 strings for the bootstrap payload."""
    if timestamp_value is None:
        return None

    return timestamp_value.isoformat()
