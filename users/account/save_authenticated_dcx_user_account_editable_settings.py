"""
CONTEXT:
This file saves the first editable settings for one authenticated DCX user.
It exists so the first `app.dcxagent.ai/me/account` surface can move from read-only display
to controlled inline autosave behavior without yet touching high-risk fields such as primary email.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG

ALLOWED_EMAIL_COMMUNICATION_PREFERENCES = {
    "announcements",
    "essential_only",
}


def save_authenticated_dcx_user_account_editable_settings_capability(
    authenticated_user_id: int,
    preferred_language_id: int | None,
    preferred_timezone_id: int | None,
    email_communication_preference: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one DCX user who should be allowed to update their own account.
        - preferred_language_id is either null or one active language id from `stephen_dcx_languages`.
        - preferred_timezone_id is either null or one active timezone id from `stephen_dcx_timezones`.
        - email_communication_preference is one allowed DCX communication-preference value.
        - The configured database is reachable.
      postconditions:
        - Saves the editable user-account settings through one upsert-shaped database write.
        - Preserves the stable user identity row instead of creating duplicate users.
        - Returns the saved editable settings payload.
      side_effects:
        - updates mutable account settings in `stephen_dcx_users`
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: authenticated_dcx_user_account_editable_settings:{authenticated_user_id}:{preferred_language_id}:{preferred_timezone_id}:{email_communication_preference}
      locks:
        - one row-level lock on `stephen_dcx_users.id`
      contention_strategy: serialize concurrent saves for the same user through a `FOR UPDATE` read before the upsert-shaped write

    NARRATIVE:
      WHY this exists:
        - The first app account edit step should prove inline autosave on low-risk mutable fields
          before email-change verification, phone capture, or broader account settings exist.
      WHEN TO USE it:
        - Use it from the app account page for preferred language and communication-preference updates only.
      WHEN NOT TO USE it:
        - Do not use it for primary-email changes.
        - Do not use it for admin-side user edits.
      WHAT CAN GO WRONG:
        - The user row can be missing.
        - The language id can be invalid or inactive.
        - The timezone id can be invalid or inactive.
        - The preference value can be unsupported.
        - Database writes can fail.
      WHAT COMES NEXT:
        - Later account mutations can add phone numbers, verified email-change flows, and other
          controlled settings while keeping this autosave path stable for the simple fields.

    TESTS:
      - saves_editable_settings_via_upsert_shaped_write
      - raises_clear_error_for_invalid_email_communication_preference
      - raises_clear_error_for_missing_user_row

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND:
          suggested_action: Confirm the authenticated user exists before retrying the account save.
          common_causes:
            - stale local debug user id
            - deleted user row
          recovery_steps:
            - Retry with a valid user id in local development.
            - Recreate the user through the signup flow if needed.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_AUTHENTICATED_DCX_USER_ACCOUNT_LANGUAGE_INVALID:
          suggested_action: Choose one active supported language and retry the save.
          common_causes:
            - stale language option
            - invalid manual request payload
          recovery_steps:
            - Refresh the account page options.
            - Retry with an active language id or null.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_AUTHENTICATED_DCX_USER_ACCOUNT_EMAIL_PREFERENCE_INVALID:
          suggested_action: Choose one supported communication preference and retry the save.
          common_causes:
            - unsupported preference value
          recovery_steps:
            - Refresh the account page options.
            - Retry with a supported value.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_AUTHENTICATED_DCX_USER_ACCOUNT_TIMEZONE_INVALID:
          suggested_action: Choose one active supported timezone and retry the save.
          common_causes:
            - stale timezone option
            - invalid manual request payload
          recovery_steps:
            - Refresh the account page options.
            - Retry with an active timezone id or null.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_AUTHENTICATED_DCX_USER_ACCOUNT_SAVE_FAILED:
          suggested_action: Confirm database health and retry the account save after the backend is stable.
          common_causes:
            - database unavailable
            - write failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend and database are healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: review the affected `stephen_dcx_users` row before retrying

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND")

    normalized_email_communication_preference = (
        email_communication_preference.strip().lower()
        if isinstance(email_communication_preference, str)
        else ""
    )
    if normalized_email_communication_preference not in ALLOWED_EMAIL_COMMUNICATION_PREFERENCES:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_EMAIL_PREFERENCE_INVALID")

    if preferred_language_id is not None and (
        not isinstance(preferred_language_id, int) or preferred_language_id <= 0
    ):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_LANGUAGE_INVALID")

    if preferred_timezone_id is not None and (
        not isinstance(preferred_timezone_id, int) or preferred_timezone_id <= 0
    ):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_TIMEZONE_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                if preferred_language_id is not None:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM stephen_dcx_languages
                        WHERE id = %s
                          AND is_active = TRUE
                        LIMIT 1
                        """,
                        (preferred_language_id,),
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_LANGUAGE_INVALID")

                if preferred_timezone_id is not None:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM stephen_dcx_timezones
                        WHERE id = %s
                          AND is_active = TRUE
                        LIMIT 1
                        """,
                        (preferred_timezone_id,),
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_TIMEZONE_INVALID")

                cursor.execute(
                    """
                    WITH existing_user AS (
                        SELECT
                            id,
                            user_uuid,
                            primary_email,
                            primary_email_confirmed,
                            primary_email_confirmed_at_ts_ms,
                            account_status,
                            last_seen_at_ts_ms,
                            created_at_ts_ms
                        FROM stephen_dcx_users
                        WHERE id = %s
                        FOR UPDATE
                    )
                    INSERT INTO stephen_dcx_users (
                        id,
                        user_uuid,
                        primary_email,
                        primary_email_confirmed,
                        primary_email_confirmed_at_ts_ms,
                        preferred_language_id,
                        preferred_timezone_id,
                        account_status,
                        email_communication_preference,
                        last_seen_at_ts_ms,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    SELECT
                        existing_user.id,
                        existing_user.user_uuid,
                        existing_user.primary_email,
                        existing_user.primary_email_confirmed,
                        existing_user.primary_email_confirmed_at_ts_ms,
                        %s,
                        %s,
                        existing_user.account_status,
                        %s,
                        existing_user.last_seen_at_ts_ms,
                        existing_user.created_at_ts_ms,
                        (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
                    FROM existing_user
                    ON CONFLICT (id)
                    DO UPDATE SET
                        preferred_language_id = EXCLUDED.preferred_language_id,
                        preferred_timezone_id = EXCLUDED.preferred_timezone_id,
                        email_communication_preference = EXCLUDED.email_communication_preference,
                        updated_at_ts_ms = EXCLUDED.updated_at_ts_ms
                    RETURNING id, preferred_language_id, preferred_timezone_id, email_communication_preference
                    """,
                    (
                        authenticated_user_id,
                        preferred_language_id,
                        preferred_timezone_id,
                        normalized_email_communication_preference,
                    ),
                )
                saved_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_SAVE_FAILED") from exc

    if saved_row is None:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND")

    return {
        "user_id": saved_row[0],
        "preferred_language_id": saved_row[1],
        "preferred_timezone_id": saved_row[2],
        "email_communication_preference": saved_row[3],
    }
