"""
CONTEXT:
This file reads content-free DCX user activity events.
It exists so the app Activity screen and admin user detail can share one safe timeline contract.

FLOW/SYSTEM:
- User or admin opens an Activity view.
- Backend returns recent activity rows for one user, newest first.

CONTRACT:
  preconditions:
    - user_id identifies one DCX user.
    - The activity table migration has been applied.
  postconditions:
    - Returns content-free activity rows.
  side_effects: []
  idempotent: true
  retry_safe: true
  async: false

NARRATIVE:
  WHY this exists:
    - DCX should show transparent account activity without leaking private message content to admins.
  WHEN TO USE it:
    - Use it for user self-service Activity and admin detail views.
  WHEN NOT TO USE it:
    - Do not use it to reconstruct message content.
  WHAT CAN GO WRONG:
    - Migration may be missing or database reads can fail.
  WHAT COMES NEXT:
    - Add pagination and retention filters.

TESTS:
  - compile smoke; integration coverage can be added with migrated test DB.

ERRORS:
  - API_DCX_USER_ACTIVITY_READ_FAILED:
      suggested_action: Apply migrations and retry after database health is restored.
      common_causes:
        - missing activity table
        - database unavailable
      recovery_steps:
        - Run migrations.
        - Retry.
      retry_safe: true

CODE:
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_user_activity_events(
    user_id: int,
    limit: int = 100,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    connect = connect_to_database or psycopg2.connect
    normalized_limit = min(max(int(limit or 100), 1), 250)
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        activity_kind,
                        surface,
                        entity_kind,
                        entity_id,
                        event_status,
                        activity_summary,
                        activity_metadata_json,
                        actor_user_id,
                        created_at_ts_ms
                    FROM stephen_dcx_user_activity_events
                    WHERE user_id = %s
                    ORDER BY created_at_ts_ms DESC, id DESC
                    LIMIT %s
                    """,
                    (user_id, normalized_limit),
                )
                rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError("API_DCX_USER_ACTIVITY_READ_FAILED") from exc

    return {
        "events": [
            {
                "activity_event_id": row[0],
                "activity_kind": row[1],
                "surface": row[2],
                "entity_kind": row[3],
                "entity_id": row[4],
                "event_status": row[5],
                "activity_summary": row[6],
                "activity_metadata": row[7] if isinstance(row[7], dict) else {},
                "actor_user_id": row[8],
                "created_at_ts_ms": row[9],
            }
            for row in rows
        ],
        "event_count": len(rows),
    }
