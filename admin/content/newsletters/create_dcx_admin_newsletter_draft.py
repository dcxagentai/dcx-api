"""
CONTEXT:
This file creates one new live newsletter-content row for the DCX admin content surface.
It exists so internal users can start composing newsletters in the same immutable multilingual
content model already used for transactional templates.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from content.shared.build_dcx_slugified_text_identifier import (
    build_dcx_slugified_text_identifier,
)
from storage.db_config import DB_CONFIG


def create_dcx_admin_newsletter_draft_capability(
    email_subject: str,
    language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_subject is one non-empty candidate newsletter subject.
        - language_code is one non-empty language code.
        - The configured database is reachable.
      postconditions:
        - Creates one new live original newsletter row in `stephen_dcx_emails`.
        - Derives one unique `email_key` from the subject.
        - Initializes `email_body` as an empty string so drafting can begin immediately.
      side_effects:
        - inserts one new live newsletter row
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - transaction-scoped advisory lock on the candidate newsletter-key base
      contention_strategy: serialize competing newsletter creation attempts for the same subject base through one advisory transaction lock

    NARRATIVE:
      WHY this exists:
        - Newsletter content should have the same stable create-then-edit workflow as content pages.
      WHEN TO USE it:
        - Use it from the `New newsletter` action in the admin newsletters list.
      WHEN NOT TO USE it:
        - Do not use it to send newsletters or create translations yet.
      WHAT CAN GO WRONG:
        - The subject can be blank.
        - The requested language can be unknown.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The editor opens the new row and the existing email save route can handle later immutable edits.

    TESTS:
      - inserts_new_live_newsletter_draft
      - appends_numeric_suffix_when_newsletter_key_already_used
      - raises_clear_error_for_blank_subject

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_DRAFT_INVALID:
          suggested_action: Enter a newsletter subject before creating the draft.
          common_causes:
            - blank subject
            - blank language code
          recovery_steps:
            - Fill in the required values and retry.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_NEWSLETTER_LANGUAGE_NOT_FOUND:
          suggested_action: Retry with one current supported language.
          common_causes:
            - unknown language code
          recovery_steps:
            - Reload supported languages and retry.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_NEWSLETTER_DRAFT_CREATE_FAILED:
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
          rollback_operation: inspect the target email key before retrying

    CODE:
    """
    normalized_email_subject = email_subject.strip()
    normalized_language_code = language_code.strip().lower()
    if normalized_email_subject == "" or normalized_language_code == "":
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_DRAFT_INVALID")

    base_email_key = build_dcx_slugified_text_identifier(normalized_email_subject)
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"dcx_newsletter_draft:{base_email_key}",),
                )
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_languages
                    WHERE language_code = %s
                    LIMIT 1
                    """,
                    (normalized_language_code,),
                )
                language_row = cursor.fetchone()
                if language_row is None:
                    raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_LANGUAGE_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT email_key
                    FROM stephen_dcx_emails
                    WHERE email_type = 'newsletter'
                    ORDER BY id ASC
                    """
                )
                existing_keys = {existing_row[0] for existing_row in cursor.fetchall()}

                next_email_key = base_email_key
                suffix_counter = 2
                while next_email_key in existing_keys:
                    next_email_key = f"{base_email_key}-{suffix_counter}"
                    suffix_counter += 1

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_emails (
                        email_type,
                        email_key,
                        language_id,
                        email_subject,
                        email_body,
                        is_original,
                        is_live
                    )
                    VALUES ('newsletter', %s, %s, %s, '', TRUE, TRUE)
                    RETURNING id
                    """,
                    (
                        next_email_key,
                        language_row[0],
                        normalized_email_subject,
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_DRAFT_CREATE_FAILED") from exc

    return {
        "email_id": inserted_row[0],
        "email_key": next_email_key,
        "language_code": normalized_language_code,
    }
