"""
CONTEXT:
This file reads basic user-level DCX LLM token usage.
It exists so the MVP app and admin surfaces can show simple per-user usage without billing logic.

FLOW/SYSTEM:
- User or admin opens a Usage view.
- Backend aggregates append-only usage events by total, day, and recent provider event.

CONTRACT:
  preconditions:
    - user_id identifies a DCX user.
    - The usage table migration has been applied.
  postconditions:
    - Returns lifetime totals, recent events, and daily totals.
  side_effects: []
  idempotent: true
  retry_safe: true
  async: false

NARRATIVE:
  WHY this exists:
    - The MVP needs a basic token account per user now, while keeping cost/budget policy separate.
  WHEN TO USE it:
    - Use it for app `/me/usage` and admin user detail/list summaries.
  WHEN NOT TO USE it:
    - Do not use it as a billing invoice.
  WHAT CAN GO WRONG:
    - Migration may be missing or database reads can fail.
  WHAT COMES NEXT:
    - Add monetary cost, budget windows, and user/account limits.

TESTS:
  - compile smoke; integration coverage can be added with migrated test DB.

ERRORS:
  - API_DCX_USER_USAGE_READ_FAILED:
      suggested_action: Apply migrations and retry after database health is restored.
      common_causes:
        - missing usage table
        - database unavailable
      recovery_steps:
        - Run migrations.
        - Retry.
      retry_safe: true

CODE:
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_dcx_user_usage_summary(
    user_id: int,
    daily_window_days: int = 30,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    connect = connect_to_database or psycopg2.connect
    normalized_daily_window_days = max(1, min(int(daily_window_days or 30), 365))
    now_utc_date = datetime.now(timezone.utc).date()
    first_usage_date = now_utc_date - timedelta(days=normalized_daily_window_days - 1)
    first_usage_ts_ms = int(datetime.combine(first_usage_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        COALESCE(SUM(prompt_token_count), 0),
                        COALESCE(SUM(candidates_token_count), 0),
                        COALESCE(SUM(total_token_count), 0),
                        COUNT(*)
                    FROM stephen_dcx_llm_usage_events
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                totals_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT
                        provider_name,
                        model_name,
                        prompt_version,
                        usage_source_kind,
                        usage_source_id,
                        prompt_token_count,
                        candidates_token_count,
                        total_token_count,
                        created_at_ts_ms
                    FROM stephen_dcx_llm_usage_events
                    WHERE user_id = %s
                    ORDER BY created_at_ts_ms DESC, id DESC
                    LIMIT 50
                    """,
                    (user_id,),
                )
                event_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        to_char((to_timestamp(created_at_ts_ms / 1000.0) AT TIME ZONE 'UTC'), 'YYYY-MM-DD') AS usage_day,
                        COALESCE(SUM(prompt_token_count), 0) AS prompt_tokens,
                        COALESCE(SUM(candidates_token_count), 0) AS candidate_tokens,
                        COALESCE(SUM(total_token_count), 0) AS total_tokens,
                        COUNT(*) AS event_count
                    FROM stephen_dcx_llm_usage_events
                      WHERE user_id = %s
                      AND created_at_ts_ms >= %s
                    GROUP BY usage_day
                    ORDER BY usage_day ASC
                    """,
                    (user_id, first_usage_ts_ms),
                )
                daily_rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError("API_DCX_USER_USAGE_READ_FAILED") from exc

    daily_totals_by_day = {
        row[0]: {
            "usage_day": row[0],
            "prompt_token_count": int(row[1] or 0),
            "candidates_token_count": int(row[2] or 0),
            "total_token_count": int(row[3] or 0),
            "event_count": int(row[4] or 0),
        }
        for row in daily_rows
    }

    daily_totals = []
    for day_offset in range(normalized_daily_window_days):
        usage_date = first_usage_date + timedelta(days=day_offset)
        usage_day = usage_date.isoformat()
        daily_totals.append(
            daily_totals_by_day.get(
                usage_day,
                {
                    "usage_day": usage_day,
                    "prompt_token_count": 0,
                    "candidates_token_count": 0,
                    "total_token_count": 0,
                    "event_count": 0,
                },
            )
        )

    return {
        "total_prompt_tokens": int(totals_row[0] or 0),
        "total_candidates_tokens": int(totals_row[1] or 0),
        "total_tokens": int(totals_row[2] or 0),
        "total_events": int(totals_row[3] or 0),
        "daily_window_days": normalized_daily_window_days,
        "recent_events": [
            {
                "provider_name": row[0],
                "model_name": row[1],
                "prompt_version": row[2],
                "usage_source_kind": row[3],
                "usage_source_id": row[4],
                "prompt_token_count": row[5],
                "candidates_token_count": row[6],
                "total_token_count": row[7],
                "created_at_ts_ms": row[8],
            }
            for row in event_rows
        ],
        "daily_totals": daily_totals,
    }
