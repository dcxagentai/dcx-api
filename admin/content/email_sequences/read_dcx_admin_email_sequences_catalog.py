"""
CONTEXT:
This file reads the admin catalog of DCX email sequences.
It exists so the internal frontend can show sequence planning rows beside newsletters without forcing
operators to leave the email area to understand what already exists.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_email_sequences_catalog_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns one ordered list of email-sequence rows.
        - Includes step-count and send-count summary values for each sequence.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Sequence planning needs one catalog surface before the detail editor can be trusted.
      WHEN TO USE it:
        - Use it from the admin sequences route.
      WHEN NOT TO USE it:
        - Do not use it for live dispatch selection; this is an editor summary.
      WHAT CAN GO WRONG:
        - The database can be unavailable.
      WHAT COMES NEXT:
        - The UI can open one sequence detail route and save steps against it.

    TESTS:
      - returns_sequence_catalog_rows_with_step_and_send_counts

    ERRORS:
      - API_DCX_ADMIN_EMAIL_SEQUENCES_CATALOG_READ_FAILED:
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
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        sequence_row.id,
                        sequence_row.sequence_key,
                        sequence_row.sequence_name,
                        sequence_row.sequence_type,
                        sequence_row.audience_type,
                        sequence_row.trigger_type,
                        sequence_row.scheduled_launch_at_ts_ms,
                        sequence_row.is_live,
                        sequence_row.created_at_ts_ms,
                        sequence_row.updated_at_ts_ms,
                        COALESCE(step_counts.total_step_count, 0) AS total_step_count,
                        COALESCE(step_counts.active_step_count, 0) AS active_step_count,
                        COALESCE(send_counts.total_send_count, 0) AS total_send_count,
                        send_counts.latest_send_at_ts_ms
                    FROM stephen_dcx_emails_sequences AS sequence_row
                    LEFT JOIN LATERAL (
                        SELECT
                            COUNT(*) AS total_step_count,
                            COUNT(*) FILTER (WHERE step_row.is_active = TRUE) AS active_step_count
                        FROM stephen_dcx_emails_sequence_steps AS step_row
                        WHERE step_row.sequence_id = sequence_row.id
                    ) AS step_counts
                      ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT
                            COUNT(*) AS total_send_count,
                            MAX(send_row.created_at_ts_ms) AS latest_send_at_ts_ms
                        FROM stephen_dcx_emails_sends AS send_row
                        WHERE send_row.source_sequence_id = sequence_row.id
                    ) AS send_counts
                      ON TRUE
                    ORDER BY sequence_row.updated_at_ts_ms DESC, sequence_row.id DESC
                    """
                )
                rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCES_CATALOG_READ_FAILED") from exc

    sequence_rows = []
    for row in rows:
        sequence_rows.append(
            {
                "sequence_id": row[0],
                "sequence_key": row[1],
                "sequence_name": row[2],
                "sequence_type": row[3],
                "audience_type": row[4],
                "trigger_type": row[5],
                "scheduled_launch_at_ts_ms": row[6],
                "is_live": row[7],
                "created_at_ts_ms": row[8],
                "updated_at_ts_ms": row[9],
                "total_step_count": row[10],
                "active_step_count": row[11],
                "total_send_count": row[12],
                "latest_send_at_ts_ms": row[13],
            }
        )

    return {
        "sequences": sequence_rows,
        "total_sequence_count": len(sequence_rows),
    }
