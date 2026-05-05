"""
CONTEXT:
This file appends one private trader-to-AI turn pair to an authenticated user's market topic.
It exists so Slice 2 can turn the seeded market-topic response into a basic back-and-forth AI chat.

FLOW/SYSTEM:
- App user opens My > Topics.
- User writes a follow-up message on a topic they own.
- DCX checks the current context size, asks Gemini for one response, and stores both turns.

CONTRACT:
  preconditions:
    - authenticated_user_id identifies the current app user.
    - market_topic_id identifies a market topic owned by that user.
    - user_turn_text is non-empty.
    - The topic conversation context is below the MVP configured character budget.
  postconditions:
    - Inserts exactly one user turn and one assistant turn when Gemini succeeds.
    - Updates the parent topic updated_at_ts_ms.
    - Returns ids and text for the appended turns.
  side_effects:
    - reads stephen_dcx_market_topics
    - reads and writes stephen_dcx_market_topic_turns
    - updates stephen_dcx_market_topics.updated_at_ts_ms
    - may call Google Gemini over HTTPS
  idempotent: false
  retry_safe: false
  async: false
  idempotency_key: not implemented for MVP app button submits
  locks:
    - row lock on stephen_dcx_market_topics during final append
  contention_strategy: latest writer wins; turn order is preserved by created_at_ts_ms and id

NARRATIVE:
  WHY this exists:
    - A market topic should be more than a static first answer. It should become the trader's
      private AI exploration space without mixing with the public forum.
  WHEN TO USE it:
    - Use it only for the authenticated owner's private topic AI chat.
  WHEN NOT TO USE it:
    - Do not use it for public forum replies or trader-to-trader trade negotiation.
  WHAT CAN GO WRONG:
    - The topic may not belong to the user, the context may be too large, Gemini may fail, or
      the save may fail after the provider response.
  WHAT COMES NEXT:
    - Later versions can add context compaction and stronger idempotency keys.

TESTS:
  - No dedicated unit test exists yet; smoke through POST /users/me/market-topics/{id}/turns.

ERRORS:
  - API_DCX_MARKET_TOPIC_CHAT_EMPTY:
      suggested_action: Add a message and retry.
      common_causes:
        - blank textarea submit
      recovery_steps:
        - Type a market-topic question or instruction.
      retry_safe: true
  - API_DCX_MARKET_TOPIC_CHAT_CONTEXT_LIMIT_REACHED:
      suggested_action: Start a new topic because this MVP chat has reached its context limit.
      common_causes:
        - too many accumulated turns
        - very long pasted input
      recovery_steps:
        - Create a new topic with the latest question.
      retry_safe: false
  - API_DCX_MARKET_TOPIC_CHAT_APPEND_FAILED:
      suggested_action: Retry after confirming the backend and Gemini provider are healthy.
      common_causes:
        - Gemini failure
        - database write failure
      recovery_steps:
        - Retry after provider/backend health is restored.
      retry_safe: false

CODE:
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from apis.gemini.generate_dcx_gemini_market_topic_chat_response import (
    generate_dcx_gemini_market_topic_chat_response,
)
from activity.record_dcx_user_activity_event import record_dcx_user_activity_event
from storage.db_config import DB_CONFIG
from usage.record_dcx_user_llm_usage_event import record_dcx_user_llm_usage_event

DCX_MARKET_TOPIC_CHAT_CONTEXT_MAX_CHARACTERS = 100000
DCX_MARKET_TOPIC_CHAT_USER_TURN_MAX_CHARACTERS = 4000


def append_authenticated_dcx_user_market_topic_ai_chat_turn(
    authenticated_user_id: int,
    market_topic_id: int,
    user_turn_text: str,
    preferred_language_code: str = "en",
    source_message_id: int | None = None,
    source_channel_type: str = "app",
    source_contact_method_id: int | None = None,
    source_route_reference_code: str | None = None,
    source_surface: str = "app",
    connect_to_database: Callable[..., Any] | None = None,
    generate_ai_response: Callable[..., dict] | None = None,
) -> dict | None:
    normalized_user_turn_text = (user_turn_text or "").strip()
    if normalized_user_turn_text == "":
        raise RuntimeError("API_DCX_MARKET_TOPIC_CHAT_EMPTY")
    if len(normalized_user_turn_text) > DCX_MARKET_TOPIC_CHAT_USER_TURN_MAX_CHARACTERS:
        raise RuntimeError("API_DCX_MARKET_TOPIC_CHAT_CONTEXT_LIMIT_REACHED")

    normalized_language_code = (preferred_language_code or "en").strip().lower() or "en"
    normalized_source_channel_type = source_channel_type.strip().lower() if isinstance(source_channel_type, str) else "app"
    if normalized_source_channel_type not in {"app", "email", "whatsapp"}:
        normalized_source_channel_type = "app"
    normalized_source_surface = source_surface.strip().lower() if isinstance(source_surface, str) else normalized_source_channel_type
    if normalized_source_surface == "":
        normalized_source_surface = normalized_source_channel_type
    normalized_source_route_reference_code = (
        source_route_reference_code.strip().upper()
        if isinstance(source_route_reference_code, str)
        else None
    )
    connect = connect_to_database or psycopg2.connect

    try:
        topic_context, prior_turns = _read_market_topic_context_and_turns(
            authenticated_user_id=authenticated_user_id,
            market_topic_id=market_topic_id,
            connect=connect,
        )
        if topic_context is None:
            return None

        existing_turn_pair = _read_existing_market_topic_turn_pair_for_source_message(
            authenticated_user_id=authenticated_user_id,
            market_topic_id=market_topic_id,
            source_message_id=source_message_id,
            connect=connect,
        )
        if existing_turn_pair is not None:
            return existing_turn_pair

        if _read_context_character_count(topic_context, prior_turns, normalized_user_turn_text) > (
            DCX_MARKET_TOPIC_CHAT_CONTEXT_MAX_CHARACTERS
        ):
            raise RuntimeError("API_DCX_MARKET_TOPIC_CHAT_CONTEXT_LIMIT_REACHED")

        ai_response = (generate_ai_response or generate_dcx_gemini_market_topic_chat_response)(
            topic_context=topic_context,
            prior_turns=prior_turns,
            user_turn_text=normalized_user_turn_text,
            preferred_language_code=normalized_language_code,
        )
        _record_market_topic_chat_usage_best_effort(
            authenticated_user_id=authenticated_user_id,
            market_topic_id=market_topic_id,
            ai_response=ai_response,
            connect=connect,
        )

        now_ts_ms = int(time.time() * 1000)
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_market_topics
                    WHERE id = %s
                      AND initiating_user_id = %s
                    FOR UPDATE
                    """,
                    (market_topic_id, authenticated_user_id),
                )
                if cursor.fetchone() is None:
                    return None

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_market_topic_turns (
                        market_topic_id,
                        turn_role,
                        source_message_id,
                        turn_text,
                        turn_metadata_json,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, 'user', %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        market_topic_id,
                        source_message_id,
                        normalized_user_turn_text,
                        Json(
                            {
                                "source_surface": normalized_source_surface,
                                "source_channel_type": normalized_source_channel_type,
                                "source_contact_method_id": source_contact_method_id,
                                "source_route_reference_code": normalized_source_route_reference_code,
                                "language_code": normalized_language_code,
                                "context_limit_max_characters": DCX_MARKET_TOPIC_CHAT_CONTEXT_MAX_CHARACTERS,
                            }
                        ),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                user_turn_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_market_topic_turns (
                        market_topic_id,
                        turn_role,
                        source_message_id,
                        turn_text,
                        turn_metadata_json,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, 'assistant', %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        market_topic_id,
                        source_message_id,
                        str(ai_response["assistant_turn_text"]).strip(),
                        Json(
                            {
                                "provider_name": ai_response.get("provider_name"),
                                "model_name": ai_response.get("model_name"),
                                "prompt_version": ai_response.get("prompt_version"),
                                "prompt_fingerprint": ai_response.get("prompt_fingerprint"),
                                "google_search_enabled": ai_response.get("google_search_enabled") is True,
                                "grounding_metadata": ai_response.get("grounding_metadata") or {},
                                "language_code": normalized_language_code,
                                "source_surface": "ai",
                                "response_route_reference_code": normalized_source_route_reference_code,
                            }
                        ),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                assistant_turn_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    UPDATE stephen_dcx_market_topics
                    SET updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (now_ts_ms, market_topic_id),
                )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_MARKET_TOPIC_CHAT_APPEND_FAILED") from exc

    return {
        "market_topic_id": market_topic_id,
        "user_turn_id": user_turn_id,
        "assistant_turn_id": assistant_turn_id,
        "assistant_turn_text": str(ai_response["assistant_turn_text"]).strip(),
        "created_at_ts_ms": now_ts_ms,
    }


def _record_market_topic_chat_usage_best_effort(
    authenticated_user_id: int,
    market_topic_id: int,
    ai_response: dict,
    connect: Callable[..., Any],
) -> None:
    try:
        record_dcx_user_llm_usage_event(
            authenticated_user_id=authenticated_user_id,
            provider_name=ai_response.get("provider_name", ""),
            model_name=ai_response.get("model_name", ""),
            prompt_version=ai_response.get("prompt_version", ""),
            usage_source_kind="market_topic_chat",
            usage_source_id=market_topic_id,
            usage_metadata=ai_response.get("usage_metadata") if isinstance(ai_response.get("usage_metadata"), dict) else {},
            connect_to_database=connect,
        )
        record_dcx_user_activity_event(
            user_id=authenticated_user_id,
            activity_kind="market_topic_chat_turn_created",
            surface="app",
            entity_kind="market_topic",
            entity_id=market_topic_id,
            activity_summary="Market topic AI chat turn created.",
            activity_metadata={},
            connect_to_database=connect,
        )
    except RuntimeError:
        pass


def _read_existing_market_topic_turn_pair_for_source_message(
    authenticated_user_id: int,
    market_topic_id: int,
    source_message_id: int | None,
    connect: Callable[..., Any],
) -> dict | None:
    if source_message_id is None or not isinstance(source_message_id, int) or source_message_id <= 0:
        return None

    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM stephen_dcx_market_topics
                WHERE id = %s
                  AND initiating_user_id = %s
                LIMIT 1
                """,
                (market_topic_id, authenticated_user_id),
            )
            if cursor.fetchone() is None:
                return None

            cursor.execute(
                """
                SELECT id, turn_role, turn_text, created_at_ts_ms
                FROM stephen_dcx_market_topic_turns
                WHERE market_topic_id = %s
                  AND source_message_id = %s
                ORDER BY created_at_ts_ms ASC, id ASC
                """,
                (market_topic_id, source_message_id),
            )
            rows = cursor.fetchall()

    user_turn_id = None
    assistant_turn_id = None
    assistant_turn_text = ""
    created_at_ts_ms = 0
    for row in rows:
        if row[1] == "user" and user_turn_id is None:
            user_turn_id = row[0]
            created_at_ts_ms = row[3]
        if row[1] == "assistant" and assistant_turn_id is None:
            assistant_turn_id = row[0]
            assistant_turn_text = row[2] or ""
            created_at_ts_ms = row[3]

    if user_turn_id is None or assistant_turn_id is None:
        return None
    return {
        "market_topic_id": market_topic_id,
        "user_turn_id": user_turn_id,
        "assistant_turn_id": assistant_turn_id,
        "assistant_turn_text": assistant_turn_text,
        "created_at_ts_ms": created_at_ts_ms,
        "deduped": True,
    }


def _read_market_topic_context_and_turns(
    authenticated_user_id: int,
    market_topic_id: int,
    connect: Callable[..., Any],
) -> tuple[dict | None, list[dict]]:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    topic_title,
                    topic_summary_text,
                    topic_scope_text,
                    topic_tags_json,
                    topic_status
                FROM stephen_dcx_market_topics
                WHERE id = %s
                  AND initiating_user_id = %s
                LIMIT 1
                """,
                (market_topic_id, authenticated_user_id),
            )
            topic_row = cursor.fetchone()
            if topic_row is None:
                return None, []

            cursor.execute(
                """
                SELECT
                    turn_role,
                    turn_text,
                    created_at_ts_ms
                FROM stephen_dcx_market_topic_turns
                WHERE market_topic_id = %s
                ORDER BY created_at_ts_ms ASC, id ASC
                """,
                (market_topic_id,),
            )
            turn_rows = cursor.fetchall()

    return (
        {
            "market_topic_id": topic_row[0],
            "topic_title": topic_row[1],
            "topic_summary_text": topic_row[2],
            "topic_scope_text": topic_row[3],
            "topic_tags_json": topic_row[4] if isinstance(topic_row[4], list) else [],
            "topic_status": topic_row[5],
        },
        [
            {
                "turn_role": row[0],
                "turn_text": row[1],
                "created_at_ts_ms": row[2],
            }
            for row in turn_rows
        ],
    )


def _read_context_character_count(topic_context: dict, prior_turns: list[dict], user_turn_text: str) -> int:
    topic_text = " ".join(
        [
            str(topic_context.get("topic_title") or ""),
            str(topic_context.get("topic_summary_text") or ""),
            str(topic_context.get("topic_scope_text") or ""),
            " ".join(topic_context.get("topic_tags_json") or []),
        ]
    )
    turns_text = "\n".join(
        f"{turn.get('turn_role')}: {turn.get('turn_text')}"
        for turn in prior_turns
    )
    return len(topic_text) + len(turns_text) + len(user_turn_text)
