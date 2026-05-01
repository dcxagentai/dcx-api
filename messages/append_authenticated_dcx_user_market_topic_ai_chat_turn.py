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
from storage.db_config import DB_CONFIG

DCX_MARKET_TOPIC_CHAT_CONTEXT_MAX_CHARACTERS = 28000
DCX_MARKET_TOPIC_CHAT_USER_TURN_MAX_CHARACTERS = 4000


def append_authenticated_dcx_user_market_topic_ai_chat_turn(
    authenticated_user_id: int,
    market_topic_id: int,
    user_turn_text: str,
    preferred_language_code: str = "en",
    connect_to_database: Callable[..., Any] | None = None,
    generate_ai_response: Callable[..., dict] | None = None,
) -> dict | None:
    normalized_user_turn_text = (user_turn_text or "").strip()
    if normalized_user_turn_text == "":
        raise RuntimeError("API_DCX_MARKET_TOPIC_CHAT_EMPTY")
    if len(normalized_user_turn_text) > DCX_MARKET_TOPIC_CHAT_USER_TURN_MAX_CHARACTERS:
        raise RuntimeError("API_DCX_MARKET_TOPIC_CHAT_CONTEXT_LIMIT_REACHED")

    normalized_language_code = (preferred_language_code or "en").strip().lower() or "en"
    connect = connect_to_database or psycopg2.connect

    try:
        topic_context, prior_turns = _read_market_topic_context_and_turns(
            authenticated_user_id=authenticated_user_id,
            market_topic_id=market_topic_id,
            connect=connect,
        )
        if topic_context is None:
            return None

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
                    VALUES (%s, 'user', NULL, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        market_topic_id,
                        normalized_user_turn_text,
                        Json(
                            {
                                "source_surface": "app",
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
                    VALUES (%s, 'assistant', NULL, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        market_topic_id,
                        str(ai_response["assistant_turn_text"]).strip(),
                        Json(
                            {
                                "provider_name": ai_response.get("provider_name"),
                                "model_name": ai_response.get("model_name"),
                                "prompt_version": ai_response.get("prompt_version"),
                                "prompt_fingerprint": ai_response.get("prompt_fingerprint"),
                                "language_code": normalized_language_code,
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

