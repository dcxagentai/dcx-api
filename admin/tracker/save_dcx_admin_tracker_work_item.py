"""
CONTEXT:
This file creates or updates one DCX admin tracker work item.
It exists so the tracker can maintain a nested map of long-term items, strategy, operations,
challenges, and concrete tasks without separate tables for each level.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG

DCX_ADMIN_TRACKER_LEVELS = {"long_term", "strategy", "operation", "battle", "task"}
DCX_ADMIN_TRACKER_PILLARS = {"legibility", "investors", "building", "customers", "other"}
DCX_ADMIN_TRACKER_STATUSES = {"not_started", "active", "waiting", "done"}


def _normalize_dcx_admin_tracker_pillars(pillars: list[str] | None, fallback_pillar: str | None) -> list[str]:
    pillar_inputs = pillars if pillars is not None else ([fallback_pillar] if fallback_pillar else [])
    normalized_pillars: list[str] = []
    for pillar_input in pillar_inputs:
        normalized_pillar = pillar_input.strip().lower()
        if normalized_pillar == "" or normalized_pillar in normalized_pillars:
            continue
        normalized_pillars.append(normalized_pillar)
    return normalized_pillars


def save_dcx_admin_tracker_work_item_capability(
    acting_admin_user_id: int,
    work_item_id: int | None,
    title: str,
    description: str,
    current_state: str,
    level: str,
    pillar: str | None,
    pillars: list[str] | None,
    status: str,
    parent_work_item_id: int | None,
    assigned_to_user_id: int | None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - acting_admin_user_id identifies the admin-capable user saving the item.
        - title is non-empty.
        - level, pillars, and status are from the tracker vocabularies.
        - parent_work_item_id is null or identifies another work item.
        - assigned_to_user_id is null or identifies one existing user.
      postconditions:
        - Creates a new work item when work_item_id is null.
        - Updates one existing work item when work_item_id is present.
        - Rejects direct or nested parent cycles.
      side_effects:
        - inserts or updates one tracker work-item row
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_admin_tracker_work_item:{work_item_id}:{title}:{level}:{pillars}:{status}:{parent_work_item_id}
      locks:
        - one row-level lock on the edited work item when updating
      contention_strategy: serialize competing edits through a FOR UPDATE lock on the target row

    NARRATIVE:
      WHY this exists:
        - DCX needs one practical shared structure for work across strategy, governance, build, investors, and customers.
      WHEN TO USE it:
        - Use it from the admin Tracker work-item editor.
      WHEN NOT TO USE it:
        - Do not use it for private user trade or account activity.
      WHAT CAN GO WRONG:
        - Required fields can be blank.
        - A parent can be stale or create a cycle.
        - The tracker migration may not exist.
      WHAT COMES NEXT:
        - Add soft archive or edit history if the internal group starts needing stronger guardrails.

    TESTS:
      - compile smoke; mutation integration tests can be added after tracker migration is in the test DB.

    ERRORS:
      - API_DCX_ADMIN_TRACKER_WORK_ITEM_INVALID:
          suggested_action: Use a non-empty title and valid level, pillar, status, and parent.
          common_causes:
            - blank title
            - invalid vocabulary value
            - self-parenting or nested parent cycle
          recovery_steps:
            - Correct the work item fields.
            - Retry the save.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_TRACKER_WORK_ITEM_NOT_FOUND:
          suggested_action: Refresh the tracker and retry from the current item list.
          common_causes:
            - stale work item id
            - item deleted outside the app
          recovery_steps:
            - Reload the tracker page.
            - Retry the save if the item still exists.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_TRACKER_WORK_ITEM_SAVE_FAILED:
          suggested_action: Retry after confirming the tracker migration and database health.
          common_causes:
            - database unavailable
            - tracker migration missing
          recovery_steps:
            - Apply the tracker migration.
            - Verify database connectivity.
            - Retry the save.
          retry_safe: true
          what_changed: unknown if transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the work item before retrying

    CODE:
    """
    normalized_title = title.strip()
    normalized_description = description.strip()
    normalized_current_state = current_state.strip()
    normalized_level = level.strip().lower()
    normalized_pillars = _normalize_dcx_admin_tracker_pillars(pillars, pillar)
    normalized_pillar = normalized_pillars[0] if normalized_pillars else ""
    normalized_status = status.strip().lower()

    if (
        acting_admin_user_id <= 0
        or normalized_title == ""
        or normalized_level not in DCX_ADMIN_TRACKER_LEVELS
        or len(normalized_pillars) == 0
        or any(normalized_pillar_value not in DCX_ADMIN_TRACKER_PILLARS for normalized_pillar_value in normalized_pillars)
        or normalized_status not in DCX_ADMIN_TRACKER_STATUSES
        or (work_item_id is not None and work_item_id <= 0)
        or (parent_work_item_id is not None and parent_work_item_id <= 0)
        or (assigned_to_user_id is not None and assigned_to_user_id <= 0)
        or (work_item_id is not None and parent_work_item_id == work_item_id)
    ):
        raise RuntimeError("API_DCX_ADMIN_TRACKER_WORK_ITEM_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                if parent_work_item_id is not None:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM public.stephen_dcx_admin_tracker_work_items
                        WHERE id = %s
                        LIMIT 1
                        """,
                        (parent_work_item_id,),
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError("API_DCX_ADMIN_TRACKER_WORK_ITEM_INVALID")

                if assigned_to_user_id is not None:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM public.stephen_dcx_users
                        WHERE id = %s
                        LIMIT 1
                        """,
                        (assigned_to_user_id,),
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError("API_DCX_ADMIN_TRACKER_WORK_ITEM_INVALID")

                if work_item_id is None:
                    cursor.execute(
                        """
                        INSERT INTO public.stephen_dcx_admin_tracker_work_items (
                            title,
                            description,
                            current_state,
                            work_item_level,
                            pillar,
                            pillars,
                            item_status,
                            parent_work_item_id,
                            assigned_to_user_id,
                            created_by_user_id,
                            updated_by_user_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            normalized_title,
                            normalized_description,
                            normalized_current_state,
                            normalized_level,
                            normalized_pillar,
                            normalized_pillars,
                            normalized_status,
                            parent_work_item_id,
                            assigned_to_user_id,
                            acting_admin_user_id,
                            acting_admin_user_id,
                        ),
                    )
                    saved_row = cursor.fetchone()
                    return {
                        "work_item_id": saved_row[0],
                        "was_created": True,
                    }

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

                if parent_work_item_id is not None:
                    cursor.execute(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT id
                            FROM public.stephen_dcx_admin_tracker_work_items
                            WHERE parent_work_item_id = %s

                            UNION ALL

                            SELECT child.id
                            FROM public.stephen_dcx_admin_tracker_work_items child
                            INNER JOIN descendants
                              ON child.parent_work_item_id = descendants.id
                        )
                        SELECT 1
                        FROM descendants
                        WHERE id = %s
                        LIMIT 1
                        """,
                        (work_item_id, parent_work_item_id),
                    )
                    if cursor.fetchone() is not None:
                        raise RuntimeError("API_DCX_ADMIN_TRACKER_WORK_ITEM_INVALID")

                cursor.execute(
                    """
                    UPDATE public.stephen_dcx_admin_tracker_work_items
                    SET
                        title = %s,
                        description = %s,
                        current_state = %s,
                        work_item_level = %s,
                        pillar = %s,
                        pillars = %s,
                        item_status = %s,
                        parent_work_item_id = %s,
                        assigned_to_user_id = %s,
                        updated_by_user_id = %s
                    WHERE id = %s
                    """,
                    (
                        normalized_title,
                        normalized_description,
                        normalized_current_state,
                        normalized_level,
                        normalized_pillar,
                        normalized_pillars,
                        normalized_status,
                        parent_work_item_id,
                        assigned_to_user_id,
                        acting_admin_user_id,
                        work_item_id,
                    ),
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_TRACKER_WORK_ITEM_SAVE_FAILED") from exc

    return {
        "work_item_id": work_item_id,
        "was_created": False,
    }
