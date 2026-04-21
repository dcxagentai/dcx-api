"""
CONTEXT:
This file records one DCX tracked-email-link click and resolves the redirect target.
It exists so newsletter and future sequence emails can send readers through one public API
redirect that logs the click before continuing to the original destination URL.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def record_dcx_email_send_link_click_and_read_redirect_target_capability(
    tracking_token: str,
    request_ip: str | None,
    request_user_agent: str | None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - tracking_token is one non-empty tracked-link token from `stephen_dcx_emails_sends_links`.
        - The configured database is reachable.
      postconditions:
        - Returns the original redirect target URL for the tracked link token.
        - Inserts one click row into `stephen_dcx_emails_sends_link_clicks`.
        - Records the current request IP and user agent when available.
      side_effects:
        - inserts one link-click row
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: click logging is append-only, so concurrent requests can insert separate rows without coordination

    NARRATIVE:
      WHY this exists:
        - Prepared newsletter send rows already snapshot tracked links, but those links need one real redirect surface before tracking becomes operational.
      WHEN TO USE it:
        - Use it from one unauthenticated public GET route that receives tracked email link clicks.
      WHEN NOT TO USE it:
        - Do not use it for browser-internal navigation or admin actions.
        - Do not use it when recipient-level click attribution is required, because the current schema only tracks clicks at the send-link level.
      WHAT CAN GO WRONG:
        - The token can be missing or unknown.
        - The database can be unavailable.
        - Some mailbox preview crawlers may create clicks before a human opens the email.
      WHAT COMES NEXT:
        - Later unsubscribe links and provider webhooks can use the same email-operational foundation.

    TESTS:
      - records_click_and_returns_redirect_target_for_valid_tracking_token
      - raises_clear_error_when_tracking_token_missing
      - raises_clear_error_when_tracking_token_not_found

    ERRORS:
      - API_DCX_EMAIL_SEND_LINK_REDIRECT_INVALID:
          suggested_action: Retry with one valid tracked link from a DCX email.
          common_causes:
            - blank tracking token
          recovery_steps:
            - Use the tracked link exactly as generated in the email.
          retry_safe: true
          what_changed: nothing was written
          rollback_needed: false
          rollback_operation: none
      - API_DCX_EMAIL_SEND_LINK_REDIRECT_NOT_FOUND:
          suggested_action: Reopen the original email and retry from the full tracked link.
          common_causes:
            - stale or malformed tracking token
            - tracked link row no longer exists
          recovery_steps:
            - Use the most recent email copy.
            - Retry from the exact tracked URL.
          retry_safe: true
          what_changed: nothing was written
          rollback_needed: false
          rollback_operation: none
      - API_DCX_EMAIL_SEND_LINK_REDIRECT_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - query failure
            - insert failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the click log table before manual replay

    CODE:
    """
    normalized_tracking_token = tracking_token.strip()
    if normalized_tracking_token == "":
        raise RuntimeError("API_DCX_EMAIL_SEND_LINK_REDIRECT_INVALID")

    connect = connect_to_database or psycopg2.connect
    current_timestamp_ms = (
        current_timestamp_ms_provider() if current_timestamp_ms_provider else _read_current_timestamp_ms()
    )

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        link_row.id,
                        link_row.email_send_id,
                        link_row.original_url
                    FROM stephen_dcx_emails_sends_links AS link_row
                    WHERE link_row.tracking_token = %s
                    LIMIT 1
                    """,
                    (normalized_tracking_token,),
                )
                link_row = cursor.fetchone()
                if link_row is None:
                    raise RuntimeError("API_DCX_EMAIL_SEND_LINK_REDIRECT_NOT_FOUND")

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_emails_sends_link_clicks (
                        email_send_id,
                        email_send_recipient_id,
                        email_send_link_id,
                        clicked_at_ts_ms,
                        request_ip,
                        request_user_agent
                    )
                    VALUES (%s, NULL, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        link_row[1],
                        link_row[0],
                        current_timestamp_ms,
                        request_ip,
                        request_user_agent,
                    ),
                )
                click_id = cursor.fetchone()[0]
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_EMAIL_SEND_LINK_REDIRECT_FAILED") from exc

    return {
        "click_id": click_id,
        "email_send_id": link_row[1],
        "email_send_link_id": link_row[0],
        "original_url": link_row[2],
        "tracking_token": normalized_tracking_token,
        "clicked_at_ts_ms": current_timestamp_ms,
    }


def _read_current_timestamp_ms() -> int:
    """Minimal contract: return one unix-milliseconds timestamp for click-log inserts."""
    return int(time.time() * 1000)
