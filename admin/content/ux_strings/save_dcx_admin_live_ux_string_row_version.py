"""
CONTEXT:
This file saves one new immutable live UX-string row version for the DCX admin surface.
It exists so internal admin editing can update multilingual UX strings while preserving
the original/version/translation model already established in `stephen_dcx_ux_strings`.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def save_dcx_admin_live_ux_string_row_version_capability(
    target_ux_string_id: int,
    next_text: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - target_ux_string_id identifies one current live row in `stephen_dcx_ux_strings`.
        - next_text is the candidate replacement text for that row and is not blank.
        - The configured database is reachable.
      postconditions:
        - Saves a new immutable live row version when the text changed.
        - Turns the previous live row off and links the new row through `version_of_id`.
        - Preserves `is_original`, `translation_of_id`, and the same group/key/language identity.
        - Returns a stable result describing whether the save was a no-op or a new live version.
      side_effects:
        - updates one current live UX-string row to `is_live = false`
        - inserts one new live UX-string row when the text changed
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_admin_live_ux_string_row_version:{target_ux_string_id}:{next_text}
      locks:
        - one row-level lock on `stephen_dcx_ux_strings.id`
      contention_strategy: serialize competing saves through a `FOR UPDATE` lock on the target live row and reject stale non-live ids

    NARRATIVE:
      WHY this exists:
        - Admin editing should respect the immutable content model instead of mutating existing UX-string rows in place.
      WHEN TO USE it:
        - Use it from the admin UX-strings edit surface when the selected-language text box is saved.
      WHEN NOT TO USE it:
        - Do not use it to create entirely new string identities or to delete rows.
      WHAT CAN GO WRONG:
        - The target row can be stale or no longer live.
        - The edited text can be blank.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The admin route can project this into autosave-friendly HTTP responses and the frontend can refetch the catalog.

    TESTS:
      - inserts_new_live_version_when_text_changes
      - returns_noop_when_text_is_unchanged
      - raises_clear_error_for_blank_text
      - raises_clear_error_for_missing_live_row

    ERRORS:
      - API_DCX_ADMIN_UX_STRING_TEXT_INVALID:
          suggested_action: Enter non-empty UX-string text before saving.
          common_causes:
            - empty textarea
            - whitespace-only text
          recovery_steps:
            - Add non-empty text and retry.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_UX_STRING_LIVE_ROW_NOT_FOUND:
          suggested_action: Refresh the catalog and retry from the current live row.
          common_causes:
            - stale admin screen selection
            - another save already created a new live version
          recovery_steps:
            - Reload the UX-string catalog.
            - Retry from the new live row if needed.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_UX_STRING_SAVE_FAILED:
          suggested_action: Retry after backend/database health is restored.
          common_causes:
            - database unavailable
            - write failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the target string key before retrying

    CODE:
    """
    if not isinstance(target_ux_string_id, int) or target_ux_string_id <= 0:
        raise RuntimeError("API_DCX_ADMIN_UX_STRING_LIVE_ROW_NOT_FOUND")

    if not isinstance(next_text, str) or next_text.strip() == "":
        raise RuntimeError("API_DCX_ADMIN_UX_STRING_TEXT_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        string_group,
                        string_key,
                        language_id,
                        text,
                        is_original,
                        translation_of_id
                    FROM stephen_dcx_ux_strings
                    WHERE id = %s
                      AND is_live = TRUE
                    FOR UPDATE
                    """,
                    (target_ux_string_id,),
                )
                existing_live_row = cursor.fetchone()

                if existing_live_row is None:
                    raise RuntimeError("API_DCX_ADMIN_UX_STRING_LIVE_ROW_NOT_FOUND")

                if existing_live_row[4] == next_text:
                    return {
                        "ux_string_id": existing_live_row[0],
                        "was_noop": True,
                    }

                cursor.execute(
                    """
                    UPDATE stephen_dcx_ux_strings
                    SET
                        is_live = FALSE,
                        updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
                    WHERE id = %s
                    """,
                    (existing_live_row[0],),
                )

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_ux_strings (
                        string_group,
                        string_key,
                        language_id,
                        text,
                        is_original,
                        is_live,
                        version_of_id,
                        translation_of_id
                    )
                    VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s)
                    RETURNING id
                    """,
                    (
                        existing_live_row[1],
                        existing_live_row[2],
                        existing_live_row[3],
                        next_text,
                        existing_live_row[5],
                        existing_live_row[0],
                        existing_live_row[6],
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_UX_STRING_SAVE_FAILED") from exc

    return {
        "ux_string_id": inserted_row[0],
        "previous_ux_string_id": existing_live_row[0],
        "was_noop": False,
    }
