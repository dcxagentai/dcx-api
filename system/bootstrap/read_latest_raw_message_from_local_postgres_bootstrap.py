"""
CONTEXT:
This file contains the first real local Postgres read capability for the DCX API bootstrap shell.
It exists to prove that the local backend can query the existing stephen_dcx database and project
one real sample record into the shared frontend bootstrap experience.

The capability is intentionally read-only and narrow:
- connect to the existing local stephen_dcx database
- select the latest row from dcx_raw_messages
- normalize the row into a frontend-safe bootstrap payload
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_latest_raw_message_from_local_postgres_bootstrap_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The local stephen_dcx Postgres database is reachable with the configured credentials.
        - The dcx_raw_messages table exists in the current local schema.
      postconditions:
        - Returns a normalized description of the latest raw message record.
        - Returns a stable empty-state payload when no raw messages exist.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why: This exists to prove the first real Postgres -> backend -> frontend roundtrip inside the MVP shell.
      when_to_use:
        - During bootstrap verification of the local DCX stack.
        - When a simple real-data sample is needed without introducing real domain APIs yet.
      when_not_to_use:
        - Do not use this as the long-term domain query shape for messages.
        - Do not use this capability for pagination, filtering, or permissions-sensitive reads.
      what_can_go_wrong:
        - The local Postgres instance may be unavailable.
        - The schema may differ from the expected alpha-spike structure.
        - The latest message may have empty text_content, requiring a fallback preview.
      what_comes_next:
        - Replace this bootstrap capability with real message/deal/thread API capabilities.
        - Move to explicit DB session infrastructure once the API grows beyond bootstrap scale.

    TESTS:
      - returns_normalized_latest_message_payload_when_row_exists
      - returns_empty_state_payload_when_no_rows_exist
      - converts_received_at_to_iso8601_string

    ERRORS:
      - API_BOOTSTRAP_LOCAL_POSTGRES_UNAVAILABLE:
          suggested_action: Confirm local Postgres is running and the dcx_storage db_config values are correct.
          common_causes:
            - local Postgres service stopped
            - wrong password or port in db_config
            - stephen_dcx database missing
          recovery_steps:
            - Start local Postgres.
            - Verify localhost:5432 and the stephen_dcx database are available.
            - Re-check db_config.py values.
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
                        dcx_sender_id,
                        dcx_receiver_id,
                        received_at
                    FROM dcx_raw_messages
                    ORDER BY received_at DESC NULLS LAST, id DESC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
    except Exception as exc:  # pragma: no cover - exercised through route tests
        raise RuntimeError("API_BOOTSTRAP_LOCAL_POSTGRES_UNAVAILABLE") from exc

    if row is None:
        return {
            "status": "empty",
            "preview_text": "No raw messages found in local Postgres.",
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
        sender_user_id,
        receiver_user_id,
        received_at,
    ) = row

    preview_text = text_content or "[message has no text_content]"

    return {
        "status": "ready",
        "preview_text": preview_text,
        "message_id": message_id,
        "message_direction": message_direction,
        "channel_type": channel_type,
        "sender_user_id": sender_user_id,
        "receiver_user_id": receiver_user_id,
        "received_at": _normalize_timestamp_to_iso8601_string(received_at),
    }


def _normalize_timestamp_to_iso8601_string(timestamp_value: datetime | None) -> str | None:
    """Minimal contract: convert datetime values into stable ISO-8601 strings for the bootstrap payload."""
    if timestamp_value is None:
        return None

    return timestamp_value.isoformat()
