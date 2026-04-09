"""
CONTEXT:
This file saves one new immutable live email-template row version for the DCX admin surface.
It exists so internal admin editing can update multilingual managed emails while preserving
the original/version/translation model already established in `stephen_dcx_emails`.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from emails.validate_live_email_template_placeholder_contract import (
    validate_live_email_template_placeholder_contract_capability,
)
from storage.db_config import DB_CONFIG


def save_dcx_admin_live_email_row_version_capability(
    target_email_id: int,
    next_email_subject: str,
    next_email_body: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - target_email_id identifies one current live row in `stephen_dcx_emails`.
        - next_email_subject is one non-empty candidate edited value.
        - next_email_body is one candidate edited value and may be empty only for newsletter drafts.
        - The configured database is reachable.
      postconditions:
        - Saves a new immutable live email row version when the subject or body changed.
        - Turns the previous live row off and links the new row through `version_of_id`.
        - Preserves `is_original`, `translation_of_id`, and the same type/key/language identity.
        - Enforces the placeholder contract for managed email templates before any new live version is inserted.
        - Returns a stable result describing whether the save was a no-op or a new live version.
      side_effects:
        - updates one current live email row to `is_live = false`
        - inserts one new live email row when the subject or body changed
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_admin_live_email_row_version:{target_email_id}:{next_email_subject}:{next_email_body}
      locks:
        - one row-level lock on `stephen_dcx_emails.id`
      contention_strategy: serialize competing saves through a `FOR UPDATE` lock on the target live row and reject stale non-live ids

    NARRATIVE:
      WHY this exists:
        - Admin email editing should preserve exact version history and should never let malformed placeholders go live.
      WHEN TO USE it:
        - Use it from the admin emails edit surface when the selected-language subject or body box is saved.
      WHEN NOT TO USE it:
        - Do not use it to create entirely new email identities or to send outbound email.
      WHAT CAN GO WRONG:
        - The target row can be stale or no longer live.
        - The edited subject can be blank.
        - The edited body can be blank for non-newsletter templates.
        - Required placeholders can be missing or malformed.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The admin route can project this into autosave-friendly HTTP responses and the frontend can refetch the catalog.

    TESTS:
      - inserts_new_live_version_when_subject_or_body_changes
      - returns_noop_when_subject_and_body_are_unchanged
      - raises_clear_error_for_blank_subject_or_body
      - raises_clear_error_for_missing_live_row
      - raises_clear_error_for_invalid_placeholder_contract

    ERRORS:
      - API_DCX_ADMIN_EMAIL_TEMPLATE_CONTENT_INVALID:
          suggested_action: Enter a non-empty email subject and, for non-newsletter templates, a non-empty body before saving.
          common_causes:
            - empty subject
            - empty body for non-newsletter templates
          recovery_steps:
            - Fill in both fields and retry.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_EMAIL_LIVE_ROW_NOT_FOUND:
          suggested_action: Refresh the catalog and retry from the current live row.
          common_causes:
            - stale admin screen selection
            - another save already created a new live version
          recovery_steps:
            - Reload the emails catalog.
            - Retry from the new live row if needed.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_EMAIL_TEMPLATE_PLACEHOLDER_INVALID:
          suggested_action: Correct the required or malformed placeholder tokens before saving.
          common_causes:
            - required placeholder removed
            - unsupported placeholder introduced
            - malformed `{{ ... }}` syntax
          recovery_steps:
            - Fix the placeholder codes in the edited template and retry.
          retry_safe: true
          what_changed: nothing was saved
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_EMAIL_SAVE_FAILED:
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
          rollback_operation: inspect the target email key before retrying

    CODE:
    """
    if not isinstance(target_email_id, int) or target_email_id <= 0:
        raise RuntimeError("API_DCX_ADMIN_EMAIL_LIVE_ROW_NOT_FOUND")

    if (
        not isinstance(next_email_subject, str)
        or next_email_subject.strip() == ""
        or not isinstance(next_email_body, str)
    ):
        raise RuntimeError("API_DCX_ADMIN_EMAIL_TEMPLATE_CONTENT_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        email_type,
                        email_key,
                        language_id,
                        email_subject,
                        email_body,
                        is_original,
                        translation_of_id
                    FROM stephen_dcx_emails
                    WHERE id = %s
                      AND is_live = TRUE
                    FOR UPDATE
                    """,
                    (target_email_id,),
                )
                existing_live_row = cursor.fetchone()

                if existing_live_row is None:
                    raise RuntimeError("API_DCX_ADMIN_EMAIL_LIVE_ROW_NOT_FOUND")

                if existing_live_row[1] != "newsletter" and next_email_body.strip() == "":
                    raise RuntimeError("API_DCX_ADMIN_EMAIL_TEMPLATE_CONTENT_INVALID")

                if (
                    existing_live_row[4] == next_email_subject
                    and existing_live_row[5] == next_email_body
                ):
                    return {
                        "email_id": existing_live_row[0],
                        "was_noop": True,
                    }

                validate_live_email_template_placeholder_contract_capability(
                    email_type=existing_live_row[1],
                    email_key=existing_live_row[2],
                    email_subject=next_email_subject,
                    email_body=next_email_body,
                )

                cursor.execute(
                    """
                    UPDATE stephen_dcx_emails
                    SET
                        is_live = FALSE,
                        updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
                    WHERE id = %s
                    """,
                    (existing_live_row[0],),
                )

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_emails (
                        email_type,
                        email_key,
                        language_id,
                        email_subject,
                        email_body,
                        is_original,
                        is_live,
                        version_of_id,
                        translation_of_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, %s)
                    RETURNING id
                    """,
                    (
                        existing_live_row[1],
                        existing_live_row[2],
                        existing_live_row[3],
                        next_email_subject,
                        next_email_body,
                        existing_live_row[6],
                        existing_live_row[0],
                        existing_live_row[7],
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError as exc:
        if str(exc).startswith(
            (
                "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_NOT_ALLOWED",
                "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_REQUIRED_MISSING",
                "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_SYNTAX_INVALID",
            )
        ):
            raise RuntimeError("API_DCX_ADMIN_EMAIL_TEMPLATE_PLACEHOLDER_INVALID") from exc
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SAVE_FAILED") from exc

    return {
        "email_id": inserted_row[0],
        "previous_email_id": existing_live_row[0],
        "was_noop": False,
    }
