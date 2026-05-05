"""
CONTEXT:
This file records one append-only DCX LLM usage event for a user.
It exists so MVP token accounting can stay simple, auditable, and provider-returned.

FLOW/SYSTEM:
- A provider boundary returns usage_metadata.
- The business capability that knows the user and source entity calls this recorder.
- User and admin usage screens aggregate the ledger.

CONTRACT:
  preconditions:
    - authenticated_user_id identifies one DCX user.
    - usage_metadata is a normalized Gemini usage metadata dict or empty dict.
    - The usage table migration has been applied.
  postconditions:
    - Inserts one usage event when total tokens are present, or a zero-token event when metadata is still useful.
    - Returns the inserted usage event id and token counts.
  side_effects:
    - writes stephen_dcx_llm_usage_events
  idempotent: false
  retry_safe: false
  async: false
  idempotency_key: none for MVP provider calls
  locks: []
  contention_strategy: append-only ledger; aggregation happens at read time

NARRATIVE:
  WHY this exists:
    - Investors/client need a basic user-level token account now, without overbuilding billing.
  WHEN TO USE it:
    - Use it immediately after a successful LLM call when the current user id is known.
  WHEN NOT TO USE it:
    - Do not use it for non-LLM events or estimated cost accounting.
  WHAT CAN GO WRONG:
    - Migration may not be applied or database may be unavailable.
  WHAT COMES NEXT:
    - Add costs, budgets, per-day caps, and provider/model selection once product usage is clearer.

TESTS:
  - compile smoke; integration coverage can be added after migration is applied in test DB.

ERRORS:
  - API_DCX_USER_LLM_USAGE_RECORD_FAILED:
      suggested_action: Apply the usage migration and retry the originating operation.
      common_causes:
        - database unavailable
        - missing usage table
      recovery_steps:
        - Run migrations.
        - Retry after backend/database health is restored.
      retry_safe: false

CODE:
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from storage.db_config import DB_CONFIG


def record_dcx_user_llm_usage_event(
    authenticated_user_id: int,
    provider_name: str,
    model_name: str,
    prompt_version: str,
    usage_source_kind: str,
    usage_source_id: int | None,
    usage_metadata: dict | None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    connect = connect_to_database or psycopg2.connect
    normalized_usage_metadata = usage_metadata if isinstance(usage_metadata, dict) else {}
    prompt_token_count = _read_usage_count(normalized_usage_metadata, "prompt_token_count")
    candidates_token_count = _read_usage_count(normalized_usage_metadata, "candidates_token_count")
    total_token_count = _read_usage_count(normalized_usage_metadata, "total_token_count")

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_llm_usage_events (
                        user_id,
                        provider_name,
                        model_name,
                        prompt_version,
                        usage_source_kind,
                        usage_source_id,
                        prompt_token_count,
                        candidates_token_count,
                        total_token_count,
                        usage_metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id, created_at_ts_ms
                    """,
                    (
                        authenticated_user_id,
                        str(provider_name or ""),
                        str(model_name or ""),
                        str(prompt_version or ""),
                        str(usage_source_kind or ""),
                        usage_source_id,
                        prompt_token_count,
                        candidates_token_count,
                        total_token_count,
                        Json(normalized_usage_metadata),
                    ),
                )
                row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError("API_DCX_USER_LLM_USAGE_RECORD_FAILED") from exc

    return {
        "usage_event_id": row[0],
        "created_at_ts_ms": row[1],
        "prompt_token_count": prompt_token_count,
        "candidates_token_count": candidates_token_count,
        "total_token_count": total_token_count,
    }


def _read_usage_count(usage_metadata: dict, key: str) -> int:
    try:
        return max(int(usage_metadata.get(key, 0) or 0), 0)
    except (TypeError, ValueError):
        return 0
