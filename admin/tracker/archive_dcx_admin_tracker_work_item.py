"""
CONTEXT:
This file archives or restores one DCX admin tracker work item.
Soft archive keeps the item recoverable while removing it from normal tracker views.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def archive_dcx_admin_tracker_work_item_capability(
    acting_admin_user_id: int,
    work_item_id: int,
    is_archived: bool,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - acting_admin_user_id identifies the admin-capable user archiving/restoring the item.
        - work_item_id identifies one existing tracker work item.
      postconditions:
        - Sets the item's archive fields.
      side_effects:
        - updates one tracker work-item row
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    if acting_admin_user_id <= 0 or work_item_id <= 0:
        raise RuntimeError("API_DCX_ADMIN_TRACKER_WORK_ITEM_ARCHIVE_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM public.stephen_dcx_admin_tracker_work_items
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (work_item_id,),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("API_DCX_ADMIN_TRACKER_WORK_ITEM_NOT_FOUND")

                cursor.execute(
                    """
                    UPDATE public.stephen_dcx_admin_tracker_work_items
                    SET
                        is_archived = %s,
                        archived_by_user_id = CASE WHEN %s THEN %s ELSE NULL END,
                        archived_at_ts_ms = CASE
                            WHEN %s THEN ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
                            ELSE NULL
                        END,
                        updated_by_user_id = %s
                    WHERE id = %s
                    """,
                    (
                        is_archived,
                        is_archived,
                        acting_admin_user_id,
                        is_archived,
                        acting_admin_user_id,
                        work_item_id,
                    ),
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_TRACKER_WORK_ITEM_ARCHIVE_FAILED") from exc

    return {
        "work_item_id": work_item_id,
        "is_archived": is_archived,
    }
