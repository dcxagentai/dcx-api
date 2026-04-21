"""
CONTEXT:
This file creates one new DCX email-sequence draft row.
It exists so the admin workspace can stage sequence planning with the same explicit create-then-edit
shape already used for newsletters and content pages.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from content.shared.build_dcx_slugified_text_identifier import (
    build_dcx_slugified_text_identifier,
)
from storage.db_config import DB_CONFIG


def create_dcx_admin_email_sequence_draft_capability(
    authenticated_admin_user_id: int,
    sequence_name: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_admin_user_id identifies one current admin/dev user.
        - sequence_name is one non-empty human-readable sequence name.
        - The configured database is reachable.
      postconditions:
        - Creates one new row in `stephen_dcx_emails_sequences`.
        - Derives one unique `sequence_key` from the submitted name.
        - Initializes the sequence as one non-live campaign with manual launch.
      side_effects:
        - inserts one new email-sequence row
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - transaction-scoped advisory lock on the candidate sequence-key base
      contention_strategy: serialize competing sequence draft creation attempts for the same base key

    NARRATIVE:
      WHY this exists:
        - Internal users need one lightweight way to start a sequence before the deeper step editor takes over.
      WHEN TO USE it:
        - Use it from the admin sequence catalog `New sequence` action.
      WHEN NOT TO USE it:
        - Do not use it to launch or dispatch sequence emails.
      WHAT CAN GO WRONG:
        - The name can be blank.
        - The database can reject the insert.
      WHAT COMES NEXT:
        - The frontend opens the detail route and the save capability owns later edits.

    TESTS:
      - inserts_new_email_sequence_draft
      - appends_numeric_suffix_when_sequence_key_already_used
      - raises_clear_error_for_blank_sequence_name

    ERRORS:
      - API_DCX_ADMIN_EMAIL_SEQUENCE_DRAFT_INVALID:
          suggested_action: Enter one sequence name before creating the draft.
          common_causes:
            - blank sequence name
            - invalid admin user id
          recovery_steps:
            - Fill in the required value and retry.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_EMAIL_SEQUENCE_DRAFT_CREATE_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - insert failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the target sequence key before retrying

    CODE:
    """
    normalized_sequence_name = sequence_name.strip()
    if authenticated_admin_user_id <= 0 or normalized_sequence_name == "":
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_DRAFT_INVALID")

    base_sequence_key = build_dcx_slugified_text_identifier(normalized_sequence_name)
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"dcx_email_sequence_draft:{base_sequence_key}",),
                )
                cursor.execute(
                    """
                    SELECT sequence_key
                    FROM stephen_dcx_emails_sequences
                    ORDER BY id ASC
                    """
                )
                existing_keys = {existing_row[0] for existing_row in cursor.fetchall()}

                next_sequence_key = base_sequence_key
                suffix_counter = 2
                while next_sequence_key in existing_keys:
                    next_sequence_key = f"{base_sequence_key}-{suffix_counter}"
                    suffix_counter += 1

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_emails_sequences (
                        sequence_key,
                        sequence_name,
                        sequence_type,
                        audience_type,
                        trigger_type,
                        is_live,
                        created_by_user_id,
                        updated_by_user_id
                    )
                    VALUES (%s, %s, 'campaign', 'all_email', 'manual_launch', FALSE, %s, %s)
                    RETURNING id
                    """,
                    (
                        next_sequence_key,
                        normalized_sequence_name,
                        authenticated_admin_user_id,
                        authenticated_admin_user_id,
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_DRAFT_CREATE_FAILED") from exc

    return {
        "sequence_id": inserted_row[0],
        "sequence_key": next_sequence_key,
    }
