"""
CONTEXT:
This file reads the first admin schedule operations catalog.
It exists so the internal workspace can list future-timed newsletter sends and scheduled sequence
launches in one place before richer timeline tooling exists.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_admin_schedule_operations_catalog_capability(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns one ordered list of schedule operations across newsletters and sequences.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Admin users need one basic timing overview without hopping across multiple content editors.
      WHEN TO USE it:
        - Use it from the admin schedule route.
      WHEN NOT TO USE it:
        - Do not use it for deep operational audits or dispatch internals.
      WHAT CAN GO WRONG:
        - The database can be unavailable.
      WHAT COMES NEXT:
        - Later the schedule surface can add reschedule, cancel, and page-publish rows.

    TESTS:
      - returns_newsletter_and_sequence_schedule_rows

    ERRORS:
      - API_DCX_ADMIN_SCHEDULE_OPERATIONS_CATALOG_READ_FAILED:
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
                        'newsletter_send' AS operation_kind,
                        send_row.id::text AS operation_id,
                        send_row.email_key_snapshot AS operation_key,
                        send_row.email_key_snapshot AS title,
                        send_row.scheduled_send_at_ts_ms AS scheduled_at_ts_ms,
                        send_row.send_status AS status,
                        COALESCE(send_row.send_summary_json ->> 'send_audience_scope', 'all') AS audience_scope,
                        'newsletter' AS source_surface
                    FROM stephen_dcx_emails_sends AS send_row
                    WHERE send_row.send_kind = 'newsletter'
                      AND send_row.send_status = 'scheduled'

                    UNION ALL

                    SELECT
                        'sequence_launch' AS operation_kind,
                        sequence_row.id::text AS operation_id,
                        sequence_row.sequence_key AS operation_key,
                        sequence_row.sequence_name AS title,
                        sequence_row.scheduled_launch_at_ts_ms AS scheduled_at_ts_ms,
                        CASE
                            WHEN sequence_row.is_live = TRUE THEN 'scheduled'
                            ELSE 'draft'
                        END AS status,
                        sequence_row.audience_type AS audience_scope,
                        'sequence' AS source_surface
                    FROM stephen_dcx_emails_sequences AS sequence_row
                    WHERE sequence_row.trigger_type = 'scheduled_launch'
                      AND sequence_row.scheduled_launch_at_ts_ms IS NOT NULL

                    ORDER BY scheduled_at_ts_ms ASC, operation_kind ASC, operation_id ASC
                    """
                )
                rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_SCHEDULE_OPERATIONS_CATALOG_READ_FAILED") from exc

    return {
        "operations": [
            {
                "operation_kind": row[0],
                "operation_id": row[1],
                "operation_key": row[2],
                "title": row[3],
                "scheduled_at_ts_ms": row[4],
                "status": row[5],
                "audience_scope": row[6],
                "source_surface": row[7],
            }
            for row in rows
        ],
        "total_operation_count": len(rows),
    }
