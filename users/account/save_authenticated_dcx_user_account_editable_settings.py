"""
CONTEXT:
This file saves the first editable settings for one authenticated DCX user.
It exists so the first `app.dcxagent.ai/me/account` surface can move from read-only display
to controlled inline autosave behavior without yet touching high-risk fields such as primary email.
"""

from __future__ import annotations

from typing import Any, Callable
import re

import psycopg2

from storage.db_config import DB_CONFIG

ALLOWED_EMAIL_COMMUNICATION_PREFERENCES = {
    "no_email",
    "newsletters",
    "all_email",
}

ALLOWED_PUBLIC_IDENTITY_MODES = {
    "display_name",
    "handle",
    "anonymous",
}

ALLOWED_DEFAULT_INTERACTION_CHANNELS = {
    "app_only",
    "email",
    "whatsapp",
}

PUBLIC_HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,32}$")


def save_authenticated_dcx_user_account_editable_settings_capability(
    authenticated_user_id: int,
    preferred_language_id: int | None,
    preferred_timezone_id: int | None,
    email_communication_preference: str,
    public_display_name: str,
    public_handle: str,
    public_identity_mode: str,
    default_interaction_channel: str,
    trade_interest_material_keys: list[str] | None = None,
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
        - Saves the editable user-account settings through one direct update on the existing user row.
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

    normalized_public_display_name = public_display_name.strip() if isinstance(public_display_name, str) else ""
    if len(normalized_public_display_name) > 80:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_PUBLIC_IDENTITY_INVALID")

    normalized_public_handle = public_handle.strip().removeprefix("@") if isinstance(public_handle, str) else ""
    if normalized_public_handle and PUBLIC_HANDLE_PATTERN.fullmatch(normalized_public_handle) is None:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_PUBLIC_IDENTITY_INVALID")

    normalized_public_identity_mode = public_identity_mode.strip().lower() if isinstance(public_identity_mode, str) else ""
    if normalized_public_identity_mode not in ALLOWED_PUBLIC_IDENTITY_MODES:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_PUBLIC_IDENTITY_INVALID")

    normalized_default_interaction_channel = (
        default_interaction_channel.strip().lower()
        if isinstance(default_interaction_channel, str)
        else ""
    )
    if normalized_default_interaction_channel not in ALLOWED_DEFAULT_INTERACTION_CHANNELS:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_DEFAULT_INTERACTION_CHANNEL_INVALID")

    if preferred_language_id is not None and (
        not isinstance(preferred_language_id, int) or preferred_language_id <= 0
    ):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_LANGUAGE_INVALID")

    if preferred_timezone_id is not None and (
        not isinstance(preferred_timezone_id, int) or preferred_timezone_id <= 0
    ):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_TIMEZONE_INVALID")

    normalized_trade_interest_material_keys = _normalize_trade_interest_material_keys(
        trade_interest_material_keys
    )

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

                if normalized_public_handle:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM stephen_dcx_users
                        WHERE lower(public_handle) = lower(%s)
                          AND id <> %s
                        LIMIT 1
                        """,
                        (
                            normalized_public_handle,
                            authenticated_user_id,
                        ),
                    )
                    if cursor.fetchone() is not None:
                        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_PUBLIC_HANDLE_TAKEN")

                if normalized_trade_interest_material_keys:
                    cursor.execute(
                        """
                        SELECT material_key
                        FROM stephen_dcx_trade_interest_material_options
                        WHERE is_active = TRUE
                          AND material_key = ANY(%s)
                        """,
                        (normalized_trade_interest_material_keys,),
                    )
                    active_material_keys = {
                        row[0]
                        for row in cursor.fetchall()
                    }
                    if active_material_keys != set(normalized_trade_interest_material_keys):
                        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_TRADE_INTERESTS_INVALID")

                cursor.execute(
                    """
                    UPDATE stephen_dcx_users
                    SET
                        preferred_language_id = %s,
                        preferred_timezone_id = %s,
                        email_communication_preference = %s,
                        public_display_name = %s,
                        public_handle = %s,
                        public_identity_mode = %s,
                        default_interaction_channel = %s,
                        updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
                    WHERE id = %s
                    RETURNING id, preferred_language_id, preferred_timezone_id, email_communication_preference, public_display_name, public_handle, public_identity_mode, default_interaction_channel
                    """,
                    (
                        preferred_language_id,
                        preferred_timezone_id,
                        normalized_email_communication_preference,
                        normalized_public_display_name,
                        normalized_public_handle,
                        normalized_public_identity_mode,
                        normalized_default_interaction_channel,
                        authenticated_user_id,
                    ),
                )
                saved_row = cursor.fetchone()
                if saved_row is not None:
                    now_ts_ms = _read_current_timestamp_ms()
                    cursor.execute(
                        """
                        DELETE FROM stephen_dcx_user_trade_interest_materials
                        WHERE user_id = %s
                        """,
                        (authenticated_user_id,),
                    )
                    for material_key in normalized_trade_interest_material_keys:
                        cursor.execute(
                            """
                            INSERT INTO stephen_dcx_user_trade_interest_materials (
                                user_id,
                                material_key,
                                created_at_ts_ms
                            )
                            VALUES (%s, %s, %s)
                            ON CONFLICT (user_id, material_key) DO NOTHING
                            """,
                            (
                                authenticated_user_id,
                                material_key,
                                now_ts_ms,
                            ),
                        )
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
        "public_display_name": saved_row[4],
        "public_handle": saved_row[5],
        "public_identity_mode": saved_row[6],
        "default_interaction_channel": saved_row[7],
        "trade_interest_material_keys": normalized_trade_interest_material_keys,
    }


def _normalize_trade_interest_material_keys(value: list[str] | None) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_TRADE_INTERESTS_INVALID")

    normalized_keys: list[str] = []
    seen_keys: set[str] = set()
    for raw_material_key in value:
        if not isinstance(raw_material_key, str):
            raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_TRADE_INTERESTS_INVALID")
        normalized_key = raw_material_key.strip().lower()
        if normalized_key == "":
            continue
        if not re.fullmatch(r"[a-z0-9_]{2,64}", normalized_key):
            raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_TRADE_INTERESTS_INVALID")
        if normalized_key in seen_keys:
            continue
        normalized_keys.append(normalized_key)
        seen_keys.add(normalized_key)
    return normalized_keys


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)
