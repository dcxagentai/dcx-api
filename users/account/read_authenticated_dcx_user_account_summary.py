"""
CONTEXT:
This file reads the minimal authenticated account summary for one DCX user.
It exists so the first `app.dcxagent.ai/me/account` surface can render real persisted
user state from `stephen_dcx_users` without coupling the frontend to raw table queries
or to future auth-provider tables.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG
from users.account.read_dcx_app_account_page_ux_strings import (
    read_dcx_app_account_page_ux_strings_capability,
)


def read_authenticated_dcx_user_account_summary_capability(
    authenticated_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one DCX user who should be allowed to view their own account.
        - The configured database is reachable.
      postconditions:
        - Returns one account-summary payload for the requested authenticated user.
        - Includes the preferred language and preferred timezone objects when those relations exist.
        - Includes the currently editable language, timezone, and communication-preference options.
        - Includes the first app-account-page UX-string map for the app frontend.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The user app needs one stable backend capability for the current-account view before
          editing, roles, or broader app surfaces exist.
      WHEN TO USE it:
        - Use it from authenticated or temporarily-debuggable app routes that need the current user's
          basic account record.
      WHEN NOT TO USE it:
        - Do not use it for admin lists of all users.
        - Do not use it as a substitute for real authorization checks at the route boundary.
      WHAT CAN GO WRONG:
        - The user id can be missing from the database.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The same route contract can later resolve the user id from the real auth/session principal
          instead of the temporary local debug query parameter.

    TESTS:
      - returns_account_summary_with_preferred_language_timezone_and_ux_strings
      - returns_account_summary_when_preferred_language_and_timezone_are_null
      - raises_clear_error_when_user_does_not_exist

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND:
          suggested_action: Confirm the authenticated user exists before retrying the account read.
          common_causes:
            - stale local debug user id
            - deleted user row
          recovery_steps:
            - Retry with a valid user id in local development.
            - Recreate the user through the signup flow if needed.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_ACCOUNT_READ_FAILED:
          suggested_action: Confirm database health and retry the account read after the backend is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend and database are healthy.
          retry_safe: true

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        u.id,
                        u.user_uuid,
                        u.primary_email,
                        u.primary_email_confirmed,
                        u.primary_email_confirmed_at_ts_ms,
                        u.primary_phone_e164,
                        u.primary_phone_confirmed,
                        u.primary_phone_confirmed_at_ts_ms,
                        u.primary_phone_channel,
                        u.account_status,
                        u.email_communication_preference,
                        u.last_seen_at_ts_ms,
                        u.created_at_ts_ms,
                        u.updated_at_ts_ms,
                        l.id,
                        l.language_code,
                        l.language_name_en,
                        l.language_name_native,
                        l.is_rtl,
                        tz.id,
                        tz.iana_name,
                        tz.display_label,
                        tz.region_label
                    FROM stephen_dcx_users u
                    LEFT JOIN stephen_dcx_languages l
                      ON l.id = u.preferred_language_id
                    LEFT JOIN stephen_dcx_timezones tz
                      ON tz.id = u.preferred_timezone_id
                    WHERE u.id = %s
                    LIMIT 1
                    """,
                    (authenticated_user_id,),
                )
                user_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT
                        id,
                        language_code,
                        language_name_en,
                        language_name_native,
                        is_rtl
                    FROM stephen_dcx_languages
                    WHERE is_active = TRUE
                    ORDER BY is_default DESC, language_code ASC
                    """
                )
                available_language_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        id,
                        iana_name,
                        display_label,
                        region_label
                    FROM stephen_dcx_timezones
                    WHERE is_active = TRUE
                    ORDER BY sort_order ASC, display_label ASC
                    """
                )
                available_timezone_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_READ_FAILED") from exc

    if user_row is None:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND")

    preferred_language = None
    if user_row[14] is not None:
        preferred_language = {
            "id": user_row[14],
            "language_code": user_row[15],
            "language_name_en": user_row[16],
            "language_name_native": user_row[17],
            "is_rtl": user_row[18],
        }

    available_languages = [
        {
            "id": available_language_row[0],
            "language_code": available_language_row[1],
            "language_name_en": available_language_row[2],
            "language_name_native": available_language_row[3],
            "is_rtl": available_language_row[4],
        }
        for available_language_row in available_language_rows
    ]

    preferred_timezone = None
    if user_row[19] is not None:
        preferred_timezone = {
            "id": user_row[19],
            "iana_name": user_row[20],
            "display_label": user_row[21],
            "region_label": user_row[22],
        }

    available_timezones = [
        {
            "id": available_timezone_row[0],
            "iana_name": available_timezone_row[1],
            "display_label": available_timezone_row[2],
            "region_label": available_timezone_row[3],
        }
        for available_timezone_row in available_timezone_rows
    ]

    ux_strings = read_dcx_app_account_page_ux_strings_capability(
        preferred_language_id=preferred_language["id"] if preferred_language else None,
        connect_to_database=connect,
    )

    return {
        "user_id": user_row[0],
        "user_uuid": str(user_row[1]),
        "primary_email": user_row[2],
        "primary_email_confirmed": user_row[3],
        "primary_email_confirmed_at_ts_ms": user_row[4],
        "primary_phone_e164": user_row[5],
        "primary_phone_confirmed": user_row[6],
        "primary_phone_confirmed_at_ts_ms": user_row[7],
        "primary_phone_channel": user_row[8],
        "account_status": user_row[9],
        "email_communication_preference": user_row[10],
        "last_seen_at_ts_ms": user_row[11],
        "created_at_ts_ms": user_row[12],
        "updated_at_ts_ms": user_row[13],
        "preferred_language": preferred_language,
        "preferred_timezone": preferred_timezone,
        "available_languages": available_languages,
        "available_timezones": available_timezones,
        "ux_strings": ux_strings,
        "available_email_communication_preferences": [
            {
                "value": "announcements",
                "label": "Announcements",
            },
            {
                "value": "essential_only",
                "label": "Essential only",
            },
        ],
    }
