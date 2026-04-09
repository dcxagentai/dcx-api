"""
CONTEXT:
This file cancels one prepared DCX newsletter send before the provider dispatcher starts.
It exists so the admin workspace can reverse a scheduled send-preparation decision without deleting
the historical recipient and link snapshots that were already prepared.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def cancel_dcx_admin_newsletter_send_capability(
    authenticated_admin_user_id: int,
    email_send_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_admin_user_id identifies one current admin/dev user.
        - email_send_id identifies one existing prepared newsletter send row.
        - The configured database is reachable.
      postconditions:
        - Marks the target prepared newsletter send row as `cancelled`.
        - Sets `cancelled_at_ts_ms`.
      side_effects:
        - updates one prepared send row
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - transaction-scoped advisory lock on the target email_send_id
      contention_strategy: serialize competing cancellation attempts for the same prepared send row

    NARRATIVE:
      WHY this exists:
        - A client user should be able to reverse a scheduled send before the delivery worker runs.
      WHEN TO USE it:
        - Use it from the admin prepared-sends list while the send is still `scheduled`.
      WHEN NOT TO USE it:
        - Do not use it after real provider sending has started.
      WHAT CAN GO WRONG:
        - The send may not exist.
        - The send may already be cancelled or beyond the `scheduled` state.
      WHAT COMES NEXT:
        - Later the dispatcher will respect this cancelled status and ignore the row.

    TESTS:
      - cancels_one_scheduled_newsletter_send
      - raises_clear_error_when_send_missing_or_not_cancellable

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_SEND_CANCEL_INVALID:
          suggested_action: Retry from one valid prepared send row.
          common_causes:
            - invalid admin user id
            - invalid email send id
          recovery_steps:
            - Reopen the prepared sends list.
            - Retry on one current send row.
          retry_safe: true
          what_changed: nothing was updated
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_NEWSLETTER_SEND_CANCEL_NOT_ALLOWED:
          suggested_action: Refresh the prepared sends list and retry only on rows still marked scheduled.
          common_causes:
            - send row missing
            - send already cancelled
            - send already moved beyond scheduled
          recovery_steps:
            - Reload the prepared sends list.
            - Retry only if the row is still scheduled.
          retry_safe: true
          what_changed: nothing was updated
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_NEWSLETTER_SEND_CANCEL_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - update failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the target send row before retrying

    CODE:
    """
    if authenticated_admin_user_id <= 0 or email_send_id <= 0:
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_SEND_CANCEL_INVALID")

    current_timestamp_ms = (
        current_timestamp_ms_provider() if current_timestamp_ms_provider else int(time.time() * 1000)
    )
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"dcx_newsletter_send_cancel:{email_send_id}",),
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_emails_sends
                    SET send_status = 'cancelled',
                        cancelled_at_ts_ms = %s,
                        updated_by_user_id = %s
                    WHERE id = %s
                      AND send_status = 'scheduled'
                    RETURNING id, send_status, cancelled_at_ts_ms
                    """,
                    (
                        current_timestamp_ms,
                        authenticated_admin_user_id,
                        email_send_id,
                    ),
                )
                updated_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_SEND_CANCEL_FAILED") from exc

    if updated_row is None:
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_SEND_CANCEL_NOT_ALLOWED")

    return {
        "email_send_id": updated_row[0],
        "send_status": updated_row[1],
        "cancelled_at_ts_ms": updated_row[2],
    }
