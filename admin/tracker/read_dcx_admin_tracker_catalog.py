"""
CONTEXT:
This file reads the first DCX admin tracker catalog.
It exists so the internal admin surface can show nested strategy, operations, battles, tasks,
and the activity updates attached to them without creating spreadsheet drift.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_tracker_catalog_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns all tracker work items plus the latest activity update stream.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin workspace needs one shared map of DCX strategy, operations, battles, tasks, and movement.
      WHEN TO USE it:
        - Use it from the admin Tracker page.
      WHEN NOT TO USE it:
        - Do not use it for user trading activity or private customer messages.
      WHAT CAN GO WRONG:
        - The tracker migration may not have been applied.
        - The database can be unavailable.
      WHAT COMES NEXT:
        - Add focused detail/pagination only if the update stream becomes large.

    TESTS:
      - compile smoke; catalog integration tests can be added after tracker migration is in the test DB.

    ERRORS:
      - API_DCX_ADMIN_TRACKER_CATALOG_READ_FAILED:
          suggested_action: Retry after confirming the tracker migration and database health.
          common_causes:
            - database unavailable
            - tracker migration missing
          recovery_steps:
            - Apply the tracker migration.
            - Verify database connectivity.
            - Retry the admin tracker page.
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
                        item.id,
                        item.title,
                        item.description,
                        item.current_state,
                        item.work_item_level,
                        item.pillar,
                        item.item_status,
                        item.parent_work_item_id,
                        parent_item.title AS parent_title,
                        item.created_by_user_id,
                        created_email_contact.normalized_value AS created_by_email,
                        item.updated_by_user_id,
                        updated_email_contact.normalized_value AS updated_by_email,
                        item.created_at_ts_ms,
                        item.updated_at_ts_ms,
                        COALESCE(update_totals.update_count, 0) AS update_count,
                        update_totals.latest_update_at_ts_ms
                    FROM public.stephen_dcx_admin_tracker_work_items item
                    LEFT JOIN public.stephen_dcx_admin_tracker_work_items parent_item
                      ON parent_item.id = item.parent_work_item_id
                    LEFT JOIN LATERAL (
                        SELECT normalized_value
                        FROM public.stephen_dcx_users_contact_methods
                        WHERE user_id = item.created_by_user_id
                          AND contact_type = %s
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) created_email_contact
                      ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT normalized_value
                        FROM public.stephen_dcx_users_contact_methods
                        WHERE user_id = item.updated_by_user_id
                          AND contact_type = %s
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) updated_email_contact
                      ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT
                            COUNT(*) AS update_count,
                            MAX(created_at_ts_ms) AS latest_update_at_ts_ms
                        FROM public.stephen_dcx_admin_tracker_updates tracker_update
                        WHERE tracker_update.work_item_id = item.id
                    ) update_totals
                      ON TRUE
                    ORDER BY
                        CASE item.work_item_level
                            WHEN 'long_term' THEN 1
                            WHEN 'strategy' THEN 2
                            WHEN 'operation' THEN 3
                            WHEN 'battle' THEN 4
                            WHEN 'task' THEN 5
                            ELSE 9
                        END,
                        item.created_at_ts_ms ASC,
                        item.id ASC
                    """,
                    ("email", "email"),
                )
                work_item_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        tracker_update.id,
                        tracker_update.work_item_id,
                        item.title AS work_item_title,
                        tracker_update.author_user_id,
                        author_email_contact.normalized_value AS author_email,
                        tracker_update.update_kind,
                        tracker_update.update_body,
                        tracker_update.created_at_ts_ms,
                        tracker_update.updated_at_ts_ms
                    FROM public.stephen_dcx_admin_tracker_updates tracker_update
                    INNER JOIN public.stephen_dcx_admin_tracker_work_items item
                      ON item.id = tracker_update.work_item_id
                    LEFT JOIN LATERAL (
                        SELECT normalized_value
                        FROM public.stephen_dcx_users_contact_methods
                        WHERE user_id = tracker_update.author_user_id
                          AND contact_type = %s
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) author_email_contact
                      ON TRUE
                    ORDER BY tracker_update.created_at_ts_ms DESC, tracker_update.id DESC
                    LIMIT 500
                    """,
                    ("email",),
                )
                update_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_TRACKER_CATALOG_READ_FAILED") from exc

    return {
        "work_items": [
            {
                "work_item_id": row[0],
                "title": row[1],
                "description": row[2],
                "current_state": row[3],
                "level": row[4],
                "pillar": row[5],
                "status": row[6],
                "parent_work_item_id": row[7],
                "parent_title": row[8],
                "created_by_user_id": row[9],
                "created_by_email": row[10],
                "updated_by_user_id": row[11],
                "updated_by_email": row[12],
                "created_at_ts_ms": row[13],
                "updated_at_ts_ms": row[14],
                "update_count": int(row[15] or 0),
                "latest_update_at_ts_ms": row[16],
            }
            for row in work_item_rows
        ],
        "updates": [
            {
                "update_id": row[0],
                "work_item_id": row[1],
                "work_item_title": row[2],
                "author_user_id": row[3],
                "author_email": row[4],
                "update_kind": row[5],
                "update_body": row[6],
                "created_at_ts_ms": row[7],
                "updated_at_ts_ms": row[8],
            }
            for row in update_rows
        ],
        "total_work_item_count": len(work_item_rows),
        "returned_update_count": len(update_rows),
    }
