"""
CONTEXT:
This file creates one first live translation row for an existing DCX transactional email identity.
It exists so the admin transactional-emails editor can expose the same missing-language creation pattern
already used on pages, categories, and newsletters.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def create_dcx_admin_email_translation_capability(
    email_key: str,
    source_language_code: str,
    target_language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_key identifies one current live transactional-email identity.
        - source_language_code identifies one current live source row for that email identity.
        - target_language_code identifies one supported language distinct from the source language.
        - The configured database is reachable.
      postconditions:
        - Creates one new live translated transactional-email row if it does not already exist.
        - Copies current source subject/body into the new target-language row as the first translation draft.
        - Links the new row back to the live original row through `translation_of_id`.
      side_effects:
        - inserts one new live translated transactional-email row
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - transaction-scoped advisory lock on email key plus target language
      contention_strategy: serialize competing translation-create attempts for the same transactional-email/language pair

    NARRATIVE:
      WHY this exists:
        - The admin transactional-email editor should use the same translation-create pattern as the rest of the CMS.
      WHEN TO USE it:
        - Use it from the admin transactional-email editor when one missing language translation is created from the source row.
      WHEN NOT TO USE it:
        - Do not use it to overwrite an existing translation.
        - Do not use it for newsletters, which already have their own route and flow.
      WHAT CAN GO WRONG:
        - The source row can be missing.
        - The target translation may already exist.
        - The target language may be invalid.
      WHAT COMES NEXT:
        - The editor opens the new translated row and autosave continues through the existing email save path.

    TESTS:
      - creates_translation_row_from_source_transactional_email
      - raises_clear_error_when_translation_already_exists

    ERRORS:
      - API_DCX_ADMIN_EMAIL_TRANSLATION_INVALID:
          suggested_action: Choose one valid source and target language pair and retry.
          common_causes:
            - blank email key
            - blank language code
            - same source and target language
          recovery_steps:
            - Reopen the transactional email from the catalog.
            - Retry with one different target language.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_EMAIL_TRANSLATION_SOURCE_NOT_FOUND:
          suggested_action: Refresh the transactional emails list and reopen the source row before retrying.
          common_causes:
            - stale source route
            - source live row no longer exists
          recovery_steps:
            - Reload the current live transactional email row.
            - Retry from the editor.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_EMAIL_TRANSLATION_ALREADY_EXISTS:
          suggested_action: Open the existing translation instead of creating a new one.
          common_causes:
            - target-language row already exists
          recovery_steps:
            - Open the existing translation from the translation list.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_EMAIL_TRANSLATION_CREATE_FAILED:
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
          rollback_operation: inspect the target transactional-email/language row before retrying

    CODE:
    """
    normalized_email_key = email_key.strip()
    normalized_source_language_code = source_language_code.strip().lower()
    normalized_target_language_code = target_language_code.strip().lower()
    if (
        normalized_email_key == ""
        or normalized_source_language_code == ""
        or normalized_target_language_code == ""
        or normalized_source_language_code == normalized_target_language_code
    ):
        raise RuntimeError("API_DCX_ADMIN_EMAIL_TRANSLATION_INVALID")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (
                        f"dcx_email_translation:{normalized_email_key}:{normalized_target_language_code}",
                    ),
                )
                cursor.execute(
                    """
                    SELECT
                        source_email.id,
                        source_email.email_type,
                        source_email.email_key,
                        source_email.email_subject,
                        source_email.email_body
                    FROM stephen_dcx_emails AS source_email
                    INNER JOIN stephen_dcx_languages AS source_language
                      ON source_language.id = source_email.language_id
                    WHERE source_email.email_key = %s
                      AND source_email.email_type <> 'newsletter'
                      AND source_email.is_live = TRUE
                      AND source_language.language_code = %s
                    LIMIT 1
                    """,
                    (normalized_email_key, normalized_source_language_code),
                )
                source_row = cursor.fetchone()
                if source_row is None:
                    raise RuntimeError("API_DCX_ADMIN_EMAIL_TRANSLATION_SOURCE_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_languages
                    WHERE language_code = %s
                    LIMIT 1
                    """,
                    (normalized_target_language_code,),
                )
                target_language_row = cursor.fetchone()
                if target_language_row is None:
                    raise RuntimeError("API_DCX_ADMIN_EMAIL_TRANSLATION_INVALID")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_emails
                    WHERE email_type = %s
                      AND email_key = %s
                      AND language_id = %s
                      AND is_live = TRUE
                    LIMIT 1
                    """,
                    (source_row[1], normalized_email_key, target_language_row[0]),
                )
                existing_translation_row = cursor.fetchone()
                if existing_translation_row is not None:
                    raise RuntimeError("API_DCX_ADMIN_EMAIL_TRANSLATION_ALREADY_EXISTS")

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_emails
                    WHERE email_type = %s
                      AND email_key = %s
                      AND is_original = TRUE
                      AND is_live = TRUE
                    LIMIT 1
                    """,
                    (source_row[1], normalized_email_key),
                )
                original_row = cursor.fetchone()
                translation_of_id = original_row[0] if original_row is not None else source_row[0]

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
                        translation_of_id
                    )
                    VALUES (%s, %s, %s, %s, %s, FALSE, TRUE, %s)
                    RETURNING id
                    """,
                    (
                        source_row[1],
                        normalized_email_key,
                        target_language_row[0],
                        source_row[3],
                        source_row[4],
                        translation_of_id,
                    ),
                )
                inserted_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_EMAIL_TRANSLATION_CREATE_FAILED") from exc

    return {
        "email_id": inserted_row[0],
        "email_key": normalized_email_key,
        "language_code": normalized_target_language_code,
    }
