"""
CONTEXT:
This file reads the first admin-facing list of DCX users.
It exists so `admin.dcxagent.ai/users` can render a real management surface from the
normalized user plus contact-method model before the full auth, roles, and permissions
system is connected.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_user_list_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns a read-only list of current DCX users ordered by latest activity/update first.
        - Includes preferred-language details when present.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first admin surface should show real user records immediately instead of waiting for
          the full admin CMS and permission model to be finished.
      WHEN TO USE it:
        - Use it from the first admin user-list route only.
      WHEN NOT TO USE it:
        - Do not use it for user self-service account views.
        - Do not use it for user mutation or admin bulk actions.
      WHAT CAN GO WRONG:
        - Database reads can fail.
      WHAT COMES NEXT:
        - Keep this route read-only until real auth and role enforcement are in place, then add
          detail views and editing flows on top.

    TESTS:
      - returns_user_rows_with_preferred_language_details
      - returns_empty_list_when_no_users_exist

    ERRORS:
      - API_DCX_ADMIN_USER_LIST_READ_FAILED:
          suggested_action: Confirm database health and retry the admin list read after the backend is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend and database are healthy.
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
                        u.id,
                        u.user_uuid,
                        primary_email_contact_method.normalized_value,
                        primary_email_contact_method.is_verified,
                        primary_email_contact_method.verified_at_ts_ms,
                        primary_phone_contact_method.normalized_value,
                        primary_phone_contact_method.is_verified,
                        primary_phone_contact_method.verified_at_ts_ms,
                        u.public_display_name,
                        u.is_tracker_team_member,
                        u.user_role,
                        u.account_status,
                        u.email_communication_preference,
                        NULLIF(
                            GREATEST(
                                COALESCE(latest_auth_session.latest_seen_at_ts_ms, 0),
                                COALESCE(latest_activity.latest_activity_at_ts_ms, 0),
                                COALESCE(u.last_seen_at_ts_ms, 0)
                            ),
                            0
                        ) AS last_seen_at_ts_ms,
                        u.created_at_ts_ms,
                        u.updated_at_ts_ms,
                        l.id,
                        l.language_code,
                        l.language_name_en,
                        l.language_name_native,
                        l.is_rtl,
                        COALESCE(usage_totals.total_token_count, 0),
                        COALESCE(usage_totals.usage_event_count, 0),
                        COALESCE(activity_totals.activity_event_count, 0)
                    FROM stephen_dcx_users u
                    LEFT JOIN LATERAL (
                        SELECT
                            normalized_value,
                            is_verified,
                            verified_at_ts_ms
                        FROM stephen_dcx_users_contact_methods
                        WHERE user_id = u.id
                          AND contact_type = %s
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) primary_email_contact_method
                      ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT
                            normalized_value,
                            is_verified,
                            verified_at_ts_ms
                        FROM stephen_dcx_users_contact_methods
                        WHERE user_id = u.id
                          AND contact_type = %s
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) primary_phone_contact_method
                      ON TRUE
                    LEFT JOIN stephen_dcx_languages l
                      ON l.id = u.preferred_language_id
                    LEFT JOIN LATERAL (
                        SELECT
                            MAX(
                                GREATEST(
                                    COALESCE(auth_session.last_seen_at_ts_ms, 0),
                                    auth_session.issued_at_ts_ms
                                )
                            ) AS latest_seen_at_ts_ms
                        FROM stephen_dcx_user_auth_sessions auth_session
                        WHERE auth_session.user_id = u.id
                    ) latest_auth_session
                      ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT MAX(created_at_ts_ms) AS latest_activity_at_ts_ms
                        FROM stephen_dcx_user_activity_events activity_event
                        WHERE activity_event.user_id = u.id
                    ) latest_activity
                      ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT
                            SUM(total_token_count) AS total_token_count,
                            COUNT(*) AS usage_event_count
                        FROM stephen_dcx_llm_usage_events
                        WHERE user_id = u.id
                    ) usage_totals
                      ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT COUNT(*) AS activity_event_count
                        FROM stephen_dcx_user_activity_events
                        WHERE user_id = u.id
                    ) activity_totals
                      ON TRUE
                    ORDER BY
                        COALESCE(
                            NULLIF(
                                GREATEST(
                                    COALESCE(latest_auth_session.latest_seen_at_ts_ms, 0),
                                    COALESCE(latest_activity.latest_activity_at_ts_ms, 0),
                                    COALESCE(u.last_seen_at_ts_ms, 0)
                                ),
                                0
                            ),
                            u.updated_at_ts_ms,
                            u.created_at_ts_ms
                        ) DESC,
                        u.id DESC
                    """
                    ,
                    ("email", "phone"),
                )
                user_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_USER_LIST_READ_FAILED") from exc

    users = []
    for user_row in user_rows:
        preferred_language = None
        if user_row[16] is not None:
            preferred_language = {
                "id": user_row[16],
                "language_code": user_row[17],
                "language_name_en": user_row[18],
                "language_name_native": user_row[19],
                "is_rtl": user_row[20],
            }

        users.append(
            {
                "user_id": user_row[0],
                "user_uuid": str(user_row[1]),
                "primary_email": user_row[2],
                "primary_email_confirmed": user_row[3],
                "primary_email_confirmed_at_ts_ms": user_row[4],
                "primary_phone": user_row[5],
                "primary_phone_confirmed": user_row[6],
                "primary_phone_confirmed_at_ts_ms": user_row[7],
                "public_display_name": user_row[8],
                "is_tracker_team_member": bool(user_row[9]),
                "user_role": user_row[10],
                "account_status": user_row[11],
                "email_communication_preference": user_row[12],
                "last_seen_at_ts_ms": user_row[13],
                "created_at_ts_ms": user_row[14],
                "updated_at_ts_ms": user_row[15],
                "preferred_language": preferred_language,
                "total_token_count": int(user_row[21] or 0) if len(user_row) > 21 else 0,
                "usage_event_count": int(user_row[22] or 0) if len(user_row) > 22 else 0,
                "activity_event_count": int(user_row[23] or 0) if len(user_row) > 23 else 0,
            }
        )

    return {
        "users": users,
        "total_user_count": len(users),
    }
