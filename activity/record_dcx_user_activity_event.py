"""
CONTEXT:
This file records one safe, content-free user activity event for DCX.
It exists so users and admins can inspect account activity without exposing private message contents.

FLOW/SYSTEM:
- A login, logout, message, trade, topic, or usage-relevant action completes.
- The capability records metadata only: kind, surface, entity ids, status, and short generic summary.
- App/admin readers render the append-only timeline.

CONTRACT:
  preconditions:
    - user_id identifies the affected user.
    - activity_kind is a short stable event name.
    - The activity table migration has been applied.
  postconditions:
    - Inserts one content-free activity row.
  side_effects:
    - writes stephen_dcx_user_activity_events
  idempotent: false
  retry_safe: false
  async: false
  idempotency_key: none for MVP event stream
  locks: []
  contention_strategy: append-only ledger

NARRATIVE:
  WHY this exists:
    - The MVP needs transparent user/account activity without letting admins read user messages.
  WHEN TO USE it:
    - Use it after meaningful user/account events complete.
  WHEN NOT TO USE it:
    - Do not store message text, attachment content, private chat content, or sensitive payloads here.
  WHAT CAN GO WRONG:
    - Migration may be missing or database writes can fail.
  WHAT COMES NEXT:
    - Add event taxonomy, export, and retention policy.

TESTS:
  - compile smoke; integration coverage can be added with migrated test DB.

ERRORS:
  - API_DCX_USER_ACTIVITY_RECORD_FAILED:
      suggested_action: Apply the activity migration and retry the originating operation.
      common_causes:
        - missing activity table
        - database unavailable
      recovery_steps:
        - Run migrations.
        - Retry.
      retry_safe: false

CODE:
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from storage.db_config import DB_CONFIG


def record_dcx_user_activity_event(
    user_id: int,
    activity_kind: str,
    surface: str,
    entity_kind: str = "",
    entity_id: int | None = None,
    event_status: str = "completed",
    activity_summary: str = "",
    activity_metadata: dict | None = None,
    actor_user_id: int | None = None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_user_activity_events (
                        user_id,
                        actor_user_id,
                        activity_kind,
                        surface,
                        entity_kind,
                        entity_id,
                        event_status,
                        activity_summary,
                        activity_metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id, created_at_ts_ms
                    """,
                    (
                        user_id,
                        actor_user_id,
                        str(activity_kind or ""),
                        str(surface or ""),
                        str(entity_kind or ""),
                        entity_id,
                        str(event_status or "completed"),
                        str(activity_summary or ""),
                        Json(activity_metadata if isinstance(activity_metadata, dict) else {}),
                    ),
                )
                row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError("API_DCX_USER_ACTIVITY_RECORD_FAILED") from exc

    return {
        "activity_event_id": row[0],
        "created_at_ts_ms": row[1],
    }
