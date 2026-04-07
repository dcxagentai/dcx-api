"""
CONTEXT:
This file marks the local DCX public-site rebuild as complete for the admin surface.
It exists so local development can establish a fresh publish baseline after the developer runs a
manual Astro rebuild instead of a Cloudflare Pages deploy.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2

from routes.users.dcx_api_routes_users_support import read_dcx_runtime_environment
from storage.db_config import DB_CONFIG

DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY = "dcx_public"


def mark_dcx_admin_public_site_local_rebuild_complete_capability(
    completed_by_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - completed_by_user_id identifies the admin user acknowledging the local rebuild.
        - The configured database is reachable.
        - `stephen_dcx_public_content_publish_state` exists.
        - The backend runtime environment is `local` or `development`.
      postconditions:
        - Records one local rebuild completion for the `dcx_public` surface.
        - Advances the accepted publish timestamp to the current local acknowledgement time.
        - Marks the publish state as `local_manual_rebuild_completed`.
      side_effects:
        - writes publish-state metadata to `stephen_dcx_public_content_publish_state`
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: last write wins for local acknowledgement timestamps

    NARRATIVE:
      WHY this exists:
        - Local development should not trigger Cloudflare, but it still needs a way to reset the
          pending-change counter after a manual local Astro rebuild.
      WHEN TO USE it:
        - Use it only after the developer has manually rebuilt or restarted `dcx_public` locally.
      WHEN NOT TO USE it:
        - Do not use it in hosted environments where Cloudflare Pages is the real deploy mechanism.
      WHAT CAN GO WRONG:
        - The route can be called outside local/development.
        - The publish-state table can be missing before its SQL is applied.
      WHAT COMES NEXT:
        - The status reader can then show zero pending changes until the next DB edit lands.

    TESTS:
      - records_local_rebuild_completion_when_runtime_is_local
      - raises_clear_error_when_called_outside_local_runtime

    ERRORS:
      - API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FORBIDDEN:
          suggested_action: Use the Cloudflare-backed publish flow outside local development.
          common_causes:
            - route called in production or staging
          recovery_steps:
            - Trigger the normal hosted publish flow instead.
          retry_safe: true
          what_changed: nothing was written
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FAILED:
          suggested_action: Confirm the publish-state SQL exists and retry after backend/database health is restored.
          common_causes:
            - publish-state table missing
            - database unavailable
          recovery_steps:
            - Apply the publish-state SQL.
            - Retry after backend health is restored.
          retry_safe: true
          what_changed: local publish baseline may or may not have been advanced
          rollback_needed: false
          rollback_operation: none

    CODE:
    """
    if not isinstance(completed_by_user_id, int) or completed_by_user_id <= 0:
        raise RuntimeError("API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FAILED")

    if read_dcx_runtime_environment() not in {"local", "development"}:
        raise RuntimeError("API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FORBIDDEN")

    connect = connect_to_database or psycopg2.connect
    read_now_ms = current_timestamp_ms or (lambda: int(time.time() * 1000))
    completed_at_ts_ms = read_now_ms()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_public_content_publish_state (
                        surface_key,
                        last_publish_status
                    )
                    VALUES (%s, %s)
                    ON CONFLICT (surface_key) DO NOTHING
                    """,
                    (
                        DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY,
                        "never_published",
                    ),
                )

                cursor.execute(
                    """
                    UPDATE stephen_dcx_public_content_publish_state
                    SET
                        last_successful_publish_at_ts_ms = %s,
                        last_successful_publish_by_user_id = %s,
                        last_attempted_publish_at_ts_ms = %s,
                        last_attempted_publish_by_user_id = %s,
                        last_publish_status = %s,
                        last_publish_message = %s,
                        updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
                    WHERE surface_key = %s
                    """,
                    (
                        completed_at_ts_ms,
                        completed_by_user_id,
                        completed_at_ts_ms,
                        completed_by_user_id,
                        "local_manual_rebuild_completed",
                        "Local public rebuild marked complete after manual dcx_public refresh.",
                        DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY,
                    ),
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FAILED") from exc

    return {
        "surface_key": DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY,
        "completed_by_user_id": completed_by_user_id,
        "completed_at_ts_ms": completed_at_ts_ms,
        "last_publish_status": "local_manual_rebuild_completed",
        "last_publish_message": "Local public rebuild marked complete after manual dcx_public refresh.",
    }
