"""
CONTEXT:
This file saves whether a user should appear on the admin Tracker Team screen.
The flag is operational and separate from account role/permissions.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def save_dcx_admin_user_tracker_team_membership_capability(
    target_user_id: int,
    is_tracker_team_member: bool,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - target_user_id identifies one existing DCX user.
      postconditions:
        - Updates that user's tracker-team flag.
      side_effects:
        - updates one stephen_dcx_users row
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    if target_user_id <= 0:
        raise RuntimeError("API_DCX_ADMIN_USER_TRACKER_TEAM_MEMBERSHIP_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE public.stephen_dcx_users
                    SET is_tracker_team_member = %s
                    WHERE id = %s
                    RETURNING id
                    """,
                    (is_tracker_team_member, target_user_id),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("API_DCX_ADMIN_USER_NOT_FOUND")
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_USER_TRACKER_TEAM_MEMBERSHIP_SAVE_FAILED") from exc

    return {
        "user_id": target_user_id,
        "is_tracker_team_member": is_tracker_team_member,
    }
