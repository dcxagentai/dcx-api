"""
CONTEXT:
This file reads the minimal authenticated account summary for one DCX user.
It exists so the first `app.dcxagent.ai/me/account` surface can render real persisted
user state from the normalized user plus contact-method model without coupling the frontend
to raw table queries or to future auth-provider tables.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG
from users.account.read_dcx_app_account_page_ux_strings import (
    read_dcx_app_account_page_ux_strings_capability,
)
from users.account_phone.read_authenticated_dcx_user_pending_whatsapp_phone_link import (
    read_authenticated_dcx_user_pending_whatsapp_phone_link,
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
        - Includes pending WhatsApp phone-link state when one delivered challenge is active.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The user app needs one stable backend capability for the current-account view before
          editing, roles, or broader app surfaces exist.
        - Email and phone now read from the normalized contact-method layer instead of duplicating
          source-of-truth contact state on the user row.
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
                        primary_email_contact_method.normalized_value,
                        primary_email_contact_method.is_verified,
                        primary_email_contact_method.verified_at_ts_ms,
                        primary_phone_contact_method.normalized_value,
                        primary_phone_contact_method.is_verified,
                        primary_phone_contact_method.verified_at_ts_ms,
                        primary_phone_identity.provider_type,
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
                            id,
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
                    LEFT JOIN LATERAL (
                        SELECT provider_type
                        FROM stephen_dcx_user_auth_identities
                        WHERE contact_method_id = primary_phone_contact_method.id
                          AND provider_type IN ('whatsapp', 'telegram', 'sms', 'phone')
                        ORDER BY
                            CASE provider_type
                                WHEN 'whatsapp' THEN 1
                                WHEN 'telegram' THEN 2
                                WHEN 'sms' THEN 3
                                ELSE 4
                            END ASC,
                            id ASC
                        LIMIT 1
                    ) primary_phone_identity
                      ON TRUE
                    LEFT JOIN stephen_dcx_languages l
                      ON l.id = u.preferred_language_id
                    LEFT JOIN stephen_dcx_timezones tz
                      ON tz.id = u.preferred_timezone_id
                    WHERE u.id = %s
                    LIMIT 1
                    """,
                    (
                        "email",
                        "phone",
                        authenticated_user_id,
                    ),
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

                cursor.execute(
                    """
                    SELECT
                        id,
                        contact_value,
                        normalized_value,
                        display_label,
                        is_primary,
                        is_login_enabled,
                        is_recovery_enabled,
                        is_notification_enabled,
                        is_verified,
                        verified_at_ts_ms,
                        verification_method,
                        is_active,
                        last_used_at_ts_ms
                    FROM stephen_dcx_users_contact_methods
                    WHERE user_id = %s
                      AND contact_type = %s
                      AND is_active = TRUE
                    ORDER BY
                        is_primary DESC,
                        is_verified DESC,
                        created_at_ts_ms ASC,
                        id ASC
                    """,
                    (
                        authenticated_user_id,
                        "email",
                    ),
                )
                email_contact_method_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        cm.id,
                        cm.contact_value,
                        cm.normalized_value,
                        cm.display_label,
                        cm.is_primary,
                        cm.is_login_enabled,
                        cm.is_recovery_enabled,
                        cm.is_notification_enabled,
                        cm.is_verified,
                        cm.verified_at_ts_ms,
                        cm.verification_method,
                        cm.is_active,
                        cm.last_used_at_ts_ms,
                        linked_identity.provider_type
                    FROM stephen_dcx_users_contact_methods cm
                    LEFT JOIN LATERAL (
                        SELECT provider_type
                        FROM stephen_dcx_user_auth_identities
                        WHERE contact_method_id = cm.id
                          AND provider_type IN ('whatsapp', 'telegram', 'sms', 'phone')
                        ORDER BY
                            CASE provider_type
                                WHEN 'whatsapp' THEN 1
                                WHEN 'telegram' THEN 2
                                WHEN 'sms' THEN 3
                                ELSE 4
                            END ASC,
                            id ASC
                        LIMIT 1
                    ) linked_identity
                      ON TRUE
                    WHERE cm.user_id = %s
                      AND cm.contact_type = %s
                      AND cm.is_active = TRUE
                    ORDER BY
                        cm.is_primary DESC,
                        cm.is_verified DESC,
                        cm.created_at_ts_ms ASC,
                        cm.id ASC
                    """,
                    (
                        authenticated_user_id,
                        "phone",
                    ),
                )
                phone_contact_method_rows = cursor.fetchall()
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

    email_contact_methods = [
        {
            "id": contact_method_row[0],
            "contact_value": contact_method_row[1],
            "normalized_value": contact_method_row[2],
            "display_label": contact_method_row[3],
            "is_primary": contact_method_row[4],
            "is_login_enabled": contact_method_row[5],
            "is_recovery_enabled": contact_method_row[6],
            "is_notification_enabled": contact_method_row[7],
            "is_verified": contact_method_row[8],
            "verified_at_ts_ms": contact_method_row[9],
            "verification_method": contact_method_row[10],
            "is_active": contact_method_row[11],
            "last_used_at_ts_ms": contact_method_row[12],
        }
        for contact_method_row in email_contact_method_rows
    ]

    phone_contact_methods = [
        {
            "id": contact_method_row[0],
            "contact_value": contact_method_row[1],
            "normalized_value": contact_method_row[2],
            "display_label": contact_method_row[3],
            "is_primary": contact_method_row[4],
            "is_login_enabled": contact_method_row[5],
            "is_recovery_enabled": contact_method_row[6],
            "is_notification_enabled": contact_method_row[7],
            "is_verified": contact_method_row[8],
            "verified_at_ts_ms": contact_method_row[9],
            "verification_method": contact_method_row[10],
            "is_active": contact_method_row[11],
            "last_used_at_ts_ms": contact_method_row[12],
            "channel": contact_method_row[13],
        }
        for contact_method_row in phone_contact_method_rows
    ]

    ux_strings = read_dcx_app_account_page_ux_strings_capability(
        preferred_language_code=preferred_language["language_code"] if preferred_language else None,
        connect_to_database=connect,
    )
    pending_whatsapp_phone_link = read_authenticated_dcx_user_pending_whatsapp_phone_link(
        authenticated_user_id=authenticated_user_id,
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
        "email_contact_methods": email_contact_methods,
        "phone_contact_methods": phone_contact_methods,
        "pending_whatsapp_phone_link": pending_whatsapp_phone_link,
        "available_languages": available_languages,
        "available_timezones": available_timezones,
        "ux_strings": ux_strings,
        "available_email_communication_preferences": [
            {
                "value": "no_email",
                "label": _read_email_communication_preference_label(
                    ux_strings=ux_strings,
                    email_communication_preference="no_email",
                ),
            },
            {
                "value": "newsletters",
                "label": _read_email_communication_preference_label(
                    ux_strings=ux_strings,
                    email_communication_preference="newsletters",
                ),
            },
            {
                "value": "all_email",
                "label": _read_email_communication_preference_label(
                    ux_strings=ux_strings,
                    email_communication_preference="all_email",
                ),
            },
        ],
    }


def _read_email_communication_preference_label(
    ux_strings: dict[str, str],
    email_communication_preference: str,
) -> str:
    if email_communication_preference == "no_email":
        return (
            ux_strings.get("email_preference_no_email")
            or ux_strings.get("email_preference_essential_only")
            or "No email"
        )

    if email_communication_preference == "newsletters":
        return (
            ux_strings.get("email_preference_newsletters")
            or ux_strings.get("email_preference_announcements")
            or "Newsletters"
        )

    if email_communication_preference == "all_email":
        return ux_strings.get("email_preference_all_email") or "All email"

    return email_communication_preference
