"""
CONTEXT:
This file edits one DCX admin tracker activity update.
It exists so internal users can correct or clarify notes, blockers, decisions, and actions
without deleting the activity history.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from admin.tracker.create_dcx_admin_tracker_update import DCX_ADMIN_TRACKER_UPDATE_KINDS
from storage.db_config import DB_CONFIG


def save_dcx_admin_tracker_update_capability(
    acting_admin_user_id: int,
    update_id: int,
    work_item_id: int,
    update_kind: str,
    update_body: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - acting_admin_user_id identifies the admin-capable user editing the update.
        - update_id identifies one existing tracker update.
        - work_item_id identifies the work item the update should belong to.
        - update_body is non-empty.
        - update_kind is one of the tracker update kinds.
      postconditions:
        - Updates one activity update.
        - Preserves the original author_user_id.
        - Records updated_by_user_id and touches the target work item.
      side_effects:
        - updates one tracker update row
        - updates one tracker work item updated_by_user_id
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_admin_tracker_update:{update_id}:{work_item_id}:{update_kind}:{update_body}

    CODE:
    """
    normalized_update_kind = update_kind.strip().lower() or "note"
    normalized_update_body = update_body.strip()

    if (
        acting_admin_user_id <= 0
        or update_id <= 0
        or work_item_id <= 0
        or normalized_update_body == ""
        or normalized_update_kind not in DCX_ADMIN_TRACKER_UPDATE_KINDS
    ):
        raise RuntimeError("API_DCX_ADMIN_TRACKER_UPDATE_INVALID")

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
                    raise RuntimeError("API_DCX_ADMIN_TRACKER_UPDATE_INVALID")

                cursor.execute(
                    """
                    SELECT id
                    FROM public.stephen_dcx_admin_tracker_updates
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (update_id,),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("API_DCX_ADMIN_TRACKER_UPDATE_NOT_FOUND")

                cursor.execute(
                    """
                    UPDATE public.stephen_dcx_admin_tracker_updates
                    SET
                        work_item_id = %s,
                        update_kind = %s,
                        update_body = %s,
                        updated_by_user_id = %s
                    WHERE id = %s
                    """,
                    (
                        work_item_id,
                        normalized_update_kind,
                        normalized_update_body,
                        acting_admin_user_id,
                        update_id,
                    ),
                )

                cursor.execute(
                    """
                    UPDATE public.stephen_dcx_admin_tracker_work_items
                    SET updated_by_user_id = %s
                    WHERE id = %s
                    """,
                    (acting_admin_user_id, work_item_id),
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_TRACKER_UPDATE_SAVE_FAILED") from exc

    return {
        "update_id": update_id,
        "work_item_id": work_item_id,
    }
