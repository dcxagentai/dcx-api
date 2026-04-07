"""
CONTEXT:
This file reads the current DCX public-site publish status for the admin surface.
It exists so the admin workspace can show whether the public static site is in sync with the
current live public UX-string rows and how many public-content edits are waiting for publish.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from languages.read_live_dcx_public_ux_strings_bundle import (
    DCX_PUBLIC_SUPPORTED_UX_STRING_GROUPS,
)
from routes.users.dcx_api_routes_users_support import read_dcx_runtime_environment
from storage.db_config import DB_CONFIG

DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY = "dcx_public"
DCX_ADMIN_PUBLIC_SITE_PENDING_CHANGES_PREVIEW_LIMIT = 8


def read_dcx_admin_public_site_publish_status_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
        - `stephen_dcx_public_content_publish_state` exists.
        - The public UX-string rows are stored in `stephen_dcx_ux_strings`.
      postconditions:
        - Returns the persisted publish-state metadata for `dcx_public`.
        - Computes the current pending public UX-string change count since the last accepted publish.
        - Returns a short preview of the current live public rows waiting to be published.
      side_effects:
        - inserts the default `dcx_public` publish-state row when the table exists but the row does not yet exist
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_admin_public_site_publish_status:dcx_public
      locks: []
      contention_strategy: rely on the unique `surface_key` constraint and idempotent upsert for row bootstrap

    NARRATIVE:
      WHY this exists:
        - The admin surface needs a simple, trustworthy way to see whether public copy edits are
          still waiting for a Cloudflare Pages rebuild.
      WHEN TO USE it:
        - Use it from the admin publish screen only.
      WHEN NOT TO USE it:
        - Do not use it as the public-site runtime content source; the public build-time API bundle
          is the content source for Astro.
      WHAT CAN GO WRONG:
        - The publish-state table can be missing before its SQL is applied.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The matching publish trigger can call the Cloudflare Pages deploy hook and then this
          reader can show the new last-attempted/last-accepted state.

    TESTS:
      - returns_publish_status_with_pending_change_count_and_preview
      - returns_zero_pending_changes_when_last_successful_publish_is_current

    ERRORS:
      - API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_STATUS_READ_FAILED:
          suggested_action: Confirm the publish-state table exists and retry after backend/database health is restored.
          common_causes:
            - publish-state SQL not applied yet
            - database unavailable
            - query failure
          recovery_steps:
            - Apply the publish-state SQL.
            - Verify backend/database health.
            - Retry the request.
          retry_safe: true
          what_changed: publish-state bootstrap row may or may not have been inserted
          rollback_needed: false
          rollback_operation: none

    CODE:
    """
    connect = connect_to_database or psycopg2.connect

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
                    SELECT
                        id,
                        surface_key,
                        last_successful_publish_at_ts_ms,
                        last_successful_publish_by_user_id,
                        last_attempted_publish_at_ts_ms,
                        last_attempted_publish_by_user_id,
                        last_publish_status,
                        last_publish_message,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    FROM stephen_dcx_public_content_publish_state
                    WHERE surface_key = %s
                    """,
                    (DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY,),
                )
                publish_state_row = cursor.fetchone()

                if publish_state_row is None:
                    raise RuntimeError("API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_STATUS_READ_FAILED")

                last_successful_publish_at_ts_ms = publish_state_row[2]

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM stephen_dcx_ux_strings AS dcx_ux_strings
                    WHERE dcx_ux_strings.is_live = TRUE
                      AND dcx_ux_strings.string_group = ANY(%s)
                      AND dcx_ux_strings.updated_at_ts_ms > COALESCE(%s, 0)
                    """,
                    (
                        list(DCX_PUBLIC_SUPPORTED_UX_STRING_GROUPS),
                        last_successful_publish_at_ts_ms,
                    ),
                )
                pending_change_count = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT
                        dcx_ux_strings.id,
                        dcx_ux_strings.string_group,
                        dcx_ux_strings.string_key,
                        dcx_languages.language_code,
                        dcx_languages.language_name_native,
                        dcx_ux_strings.updated_at_ts_ms
                    FROM stephen_dcx_ux_strings AS dcx_ux_strings
                    JOIN stephen_dcx_languages AS dcx_languages
                      ON dcx_languages.id = dcx_ux_strings.language_id
                    WHERE dcx_ux_strings.is_live = TRUE
                      AND dcx_ux_strings.string_group = ANY(%s)
                      AND dcx_ux_strings.updated_at_ts_ms > COALESCE(%s, 0)
                    ORDER BY dcx_ux_strings.updated_at_ts_ms DESC, dcx_ux_strings.id DESC
                    LIMIT %s
                    """,
                    (
                        list(DCX_PUBLIC_SUPPORTED_UX_STRING_GROUPS),
                        last_successful_publish_at_ts_ms,
                        DCX_ADMIN_PUBLIC_SITE_PENDING_CHANGES_PREVIEW_LIMIT,
                    ),
                )
                pending_preview_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_STATUS_READ_FAILED") from exc

    return {
        "surface_key": publish_state_row[1],
        "runtime_environment": read_dcx_runtime_environment(),
        "publish_execution_mode": (
            "local_manual_rebuild"
            if read_dcx_runtime_environment() in {"local", "development"}
            else "cloudflare_pages_hook"
        ),
        "last_successful_publish_at_ts_ms": publish_state_row[2],
        "last_successful_publish_by_user_id": publish_state_row[3],
        "last_attempted_publish_at_ts_ms": publish_state_row[4],
        "last_attempted_publish_by_user_id": publish_state_row[5],
        "last_publish_status": publish_state_row[6],
        "last_publish_message": publish_state_row[7],
        "created_at_ts_ms": publish_state_row[8],
        "updated_at_ts_ms": publish_state_row[9],
        "pending_change_count": pending_change_count,
        "pending_changes_preview": [
            {
                "ux_string_id": pending_preview_row[0],
                "string_group": pending_preview_row[1],
                "string_key": pending_preview_row[2],
                "language_code": pending_preview_row[3],
                "language_name_native": pending_preview_row[4],
                "updated_at_ts_ms": pending_preview_row[5],
            }
            for pending_preview_row in pending_preview_rows
        ],
        "public_managed_groups": list(DCX_PUBLIC_SUPPORTED_UX_STRING_GROUPS),
    }
