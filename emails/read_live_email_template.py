"""
CONTEXT:
This file reads one live DCX email template from the database.
It exists so transactional, newsletter, and sequence email builders can all fetch
their current subject/body copy from `stephen_dcx_emails` without duplicating
language fallback logic in each business flow.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_live_email_template_capability(
    email_type: str,
    email_key: str,
    language_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_type identifies one stored email family such as `transactional`.
        - email_key identifies one stored live email template inside that family.
        - language_code is the requested language code for delivery.
      postconditions:
        - Returns the live language-specific template when it exists.
        - Falls back to the live original template when that language is not yet translated.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Email delivery flows need one reusable way to resolve the current live template without
          hardcoding subjects and body text in signup/auth capabilities.
      WHEN TO USE it:
        - Use it inside backend email draft builders right before placeholder rendering.
      WHEN NOT TO USE it:
        - Do not use it for frontend UX strings or browser-facing content bundles.
      WHAT CAN GO WRONG:
        - The live template can be missing.
        - Database access can fail.
      WHAT COMES NEXT:
        - The template renderer can safely substitute only the placeholders allowed for that email purpose.

    TESTS:
      - returns_requested_live_translation_when_language_exists
      - falls_back_to_live_original_when_translation_missing
      - raises_clear_error_when_no_live_template_exists

    ERRORS:
      - API_LIVE_EMAIL_TEMPLATE_NOT_FOUND:
          suggested_action: Seed or publish the requested live email template before sending.
          common_causes:
            - missing live row for the email_key
            - template not translated or no original row published
          recovery_steps:
            - Insert or publish the required email template row.
            - Retry delivery after the template is live.
          retry_safe: true
      - API_LIVE_EMAIL_TEMPLATE_READ_FAILED:
          suggested_action: Confirm database health and retry after the backend is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the database is healthy.
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
                        e.id,
                        l.language_code,
                        e.email_subject,
                        e.email_body,
                        e.is_original
                    FROM stephen_dcx_emails e
                    JOIN stephen_dcx_languages l
                      ON l.id = e.language_id
                    WHERE e.email_type = %s
                      AND e.email_key = %s
                      AND e.is_live = TRUE
                      AND (
                        l.language_code = %s
                        OR e.is_original = TRUE
                      )
                    ORDER BY
                      CASE WHEN l.language_code = %s THEN 0 ELSE 1 END,
                      CASE WHEN e.is_original = TRUE THEN 0 ELSE 1 END
                    LIMIT 1
                    """,
                    (
                        email_type,
                        email_key,
                        language_code,
                        language_code,
                    ),
                )
                template_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_LIVE_EMAIL_TEMPLATE_READ_FAILED") from exc

    if template_row is None:
        raise RuntimeError("API_LIVE_EMAIL_TEMPLATE_NOT_FOUND")

    return {
        "template_id": template_row[0],
        "language_code": template_row[1],
        "email_subject": template_row[2],
        "email_body": template_row[3],
        "is_original": template_row[4],
    }
