"""
CONTEXT:
This file reads one admin-facing DCX email-sequence detail payload.
It exists so the sequence editor can load one sequence plus its ordered step list without forcing the
frontend to stitch together multiple backend calls.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_email_sequence_detail_capability(
    sequence_key: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - sequence_key is one non-empty sequence identity key.
        - The configured database is reachable.
      postconditions:
        - Returns one sequence detail payload plus its ordered step rows.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The sequence editor needs one canonical detail payload.
      WHEN TO USE it:
        - Use it from the admin sequence detail route.
      WHEN NOT TO USE it:
        - Do not use it as a public runtime config surface.
      WHAT CAN GO WRONG:
        - The sequence can be missing.
        - The database can be unavailable.
      WHAT COMES NEXT:
        - The frontend can save the edited sequence and step list back through one write route.

    TESTS:
      - returns_sequence_detail_with_ordered_steps
      - raises_clear_error_when_sequence_missing

    ERRORS:
      - API_DCX_ADMIN_EMAIL_SEQUENCE_DETAIL_NOT_FOUND:
          suggested_action: Refresh the sequences list and reopen the current row.
          common_causes:
            - stale sequence route
            - deleted sequence
          recovery_steps:
            - Reload the catalog.
            - Retry from the current sequence row.
          retry_safe: true
      - API_DCX_ADMIN_EMAIL_SEQUENCE_DETAIL_READ_FAILED:
          suggested_action: Retry after confirming the backend and database are healthy.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry when the backend is healthy.
          retry_safe: true

    CODE:
    """
    normalized_sequence_key = sequence_key.strip()
    if normalized_sequence_key == "":
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_DETAIL_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        sequence_key,
                        sequence_name,
                        sequence_type,
                        audience_type,
                        trigger_type,
                        scheduled_launch_at_ts_ms,
                        is_live,
                        created_by_user_id,
                        updated_by_user_id,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    FROM stephen_dcx_emails_sequences
                    WHERE sequence_key = %s
                    LIMIT 1
                    """,
                    (normalized_sequence_key,),
                )
                sequence_row = cursor.fetchone()
                if sequence_row is None:
                    raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_DETAIL_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT
                        step_row.id,
                        step_row.step_key,
                        step_row.step_name,
                        step_row.step_order,
                        step_row.source_email_id,
                        step_row.delay_minutes_from_trigger,
                        step_row.is_active,
                        step_row.created_at_ts_ms,
                        step_row.updated_at_ts_ms,
                        email_row.email_key,
                        email_row.email_subject,
                        email_row.email_type,
                        language_row.language_code
                    FROM stephen_dcx_emails_sequence_steps AS step_row
                    INNER JOIN stephen_dcx_emails AS email_row
                      ON email_row.id = step_row.source_email_id
                    INNER JOIN stephen_dcx_languages AS language_row
                      ON language_row.id = email_row.language_id
                    WHERE step_row.sequence_id = %s
                    ORDER BY step_row.step_order ASC, step_row.id ASC
                    """,
                    (sequence_row[0],),
                )
                step_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_DETAIL_READ_FAILED") from exc

    return {
        "sequence_id": sequence_row[0],
        "sequence_key": sequence_row[1],
        "sequence_name": sequence_row[2],
        "sequence_type": sequence_row[3],
        "audience_type": sequence_row[4],
        "trigger_type": sequence_row[5],
        "scheduled_launch_at_ts_ms": sequence_row[6],
        "is_live": sequence_row[7],
        "created_by_user_id": sequence_row[8],
        "updated_by_user_id": sequence_row[9],
        "created_at_ts_ms": sequence_row[10],
        "updated_at_ts_ms": sequence_row[11],
        "steps": [
            {
                "sequence_step_id": step_row[0],
                "step_key": step_row[1],
                "step_name": step_row[2],
                "step_order": step_row[3],
                "source_email_id": step_row[4],
                "delay_minutes_from_trigger": step_row[5],
                "is_active": step_row[6],
                "created_at_ts_ms": step_row[7],
                "updated_at_ts_ms": step_row[8],
                "source_email_key": step_row[9],
                "source_email_subject": step_row[10],
                "source_email_type": step_row[11],
                "source_language_code": step_row[12],
            }
            for step_row in step_rows
        ],
    }
