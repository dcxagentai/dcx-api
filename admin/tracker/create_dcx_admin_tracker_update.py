"""
CONTEXT:
This file creates one activity update for a DCX admin tracker work item.
It exists so the tracker can act as the shared activity log for strategy, operations,
challenges, and tasks as the small internal group moves work forward.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG

DCX_ADMIN_TRACKER_UPDATE_KINDS = {"note", "progress", "blocker", "decision", "question", "action"}


def create_dcx_admin_tracker_update_capability(
    acting_admin_user_id: int,
    work_item_id: int,
    update_kind: str,
    update_body: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - acting_admin_user_id identifies the admin-capable user writing the update.
        - work_item_id identifies one tracker work item.
        - update_body is non-empty.
        - update_kind is one of the tracker update kinds.
      postconditions:
        - Inserts one activity update attached to the work item.
        - Marks the work item as touched by the acting admin user.
      side_effects:
        - inserts one tracker update row
        - updates the parent work item's updated_by_user_id
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - one row-level lock on the target work item
      contention_strategy: serialize update attachment through a FOR UPDATE lock on the parent work item

    NARRATIVE:
      WHY this exists:
        - The update stream is how people record what changed, what is blocked, what was decided, and what happens next.
      WHEN TO USE it:
        - Use it from the Tracker update composer.
      WHEN NOT TO USE it:
        - Do not use it as a private diary disconnected from a work item.
      WHAT CAN GO WRONG:
        - The work item can be stale or missing.
        - The update body can be blank.
      WHAT COMES NEXT:
        - Add editable updates only if the internal group needs corrections after posting.

    TESTS:
      - compile smoke; mutation integration tests can be added after tracker migration is in the test DB.

    ERRORS:
      - API_DCX_ADMIN_TRACKER_UPDATE_INVALID:
          suggested_action: Choose an existing work item and write a non-empty update.
          common_causes:
            - blank body
            - invalid update kind
            - missing work item
          recovery_steps:
            - Refresh the tracker.
            - Re-enter the update.
            - Retry the post.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_TRACKER_UPDATE_CREATE_FAILED:
          suggested_action: Retry after confirming the tracker migration and database health.
          common_causes:
            - database unavailable
            - tracker migration missing
          recovery_steps:
            - Apply the tracker migration.
            - Verify database connectivity.
            - Retry the update.
          retry_safe: false
          what_changed: unknown if transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the update stream before retrying

    CODE:
    """
    normalized_update_kind = update_kind.strip().lower() or "note"
    normalized_update_body = update_body.strip()

    if (
        acting_admin_user_id <= 0
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
                    INSERT INTO public.stephen_dcx_admin_tracker_updates (
                        work_item_id,
                        author_user_id,
                        updated_by_user_id,
                        update_kind,
                        update_body
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        work_item_id,
                        acting_admin_user_id,
                        acting_admin_user_id,
                        normalized_update_kind,
                        normalized_update_body,
                    ),
                )
                inserted_row = cursor.fetchone()

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
        raise RuntimeError("API_DCX_ADMIN_TRACKER_UPDATE_CREATE_FAILED") from exc

    return {
        "update_id": inserted_row[0],
        "work_item_id": work_item_id,
    }
