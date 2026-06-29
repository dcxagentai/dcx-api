"""
CONTEXT:
This file creates one direct authenticated-user AI chat while reusing the existing
market-topic tables as the backing store.
It exists so users can intentionally start a personal AI chat without sending a message through
the trade/non-trade classifier first.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from activity.record_dcx_user_activity_event import record_dcx_user_activity_event
from apis.gemini.generate_dcx_gemini_market_topic_chat_response import (
    generate_dcx_gemini_market_topic_chat_response,
)
from apis.gemini.generate_dcx_gemini_user_content_policy_check import (
    generate_dcx_gemini_user_content_policy_check,
)
from storage.db_config import DB_CONFIG
from usage.record_dcx_user_llm_usage_event import record_dcx_user_llm_usage_event

DCX_AI_CHAT_INITIAL_USER_TURN_MAX_CHARACTERS = 4000


def create_authenticated_dcx_user_ai_chat(
    authenticated_user_id: int,
    initial_user_turn_text: str,
    preferred_language_code: str = "en",
    connect_to_database: Callable[..., Any] | None = None,
    generate_ai_response: Callable[..., dict] | None = None,
    check_content_policy: Callable[..., dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one current DCX user.
        - initial_user_turn_text is non-empty and below the MVP per-turn limit.
      postconditions:
        - Runs the shared user-content policy check.
        - Creates one hidden source contact-message row, one workflow item, one AI-chat topic,
          and the first user/assistant turn pair.
        - Returns the created market_topic_id.
      side_effects:
        - writes to stephen_dcx_contact_messages
        - writes to stephen_dcx_message_workflow_items
        - writes to stephen_dcx_market_topics
        - writes to stephen_dcx_market_topic_turns
        - may call Google Gemini
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - Users now need AI Chats as a direct personal habit surface, not only as a side effect of
          message classification.
      WHEN TO USE it:
        - Use it from `POST /ai/chats` and explicit "New AI Chat" UI actions.
      WHEN NOT TO USE it:
        - Do not use it for trade-object extraction; trade routing still uses the message pipeline.

    ERRORS:
      - API_DCX_AI_CHAT_EMPTY:
          suggested_action: Add an initial AI chat message and retry.
          retry_safe: true
      - API_DCX_AI_CHAT_CONTEXT_LIMIT_REACHED:
          suggested_action: Shorten the first message and retry.
          retry_safe: true
      - API_DCX_AI_CHAT_PROHIBITED:
          suggested_action: Rewrite the message without prohibited content.
          retry_safe: true
      - API_DCX_AI_CHAT_CREATE_FAILED:
          suggested_action: Retry after the backend and AI provider are healthy.
          retry_safe: false

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_DCX_AI_CHAT_USER_NOT_FOUND")

    normalized_turn_text = initial_user_turn_text.strip() if isinstance(initial_user_turn_text, str) else ""
    if normalized_turn_text == "":
        raise RuntimeError("API_DCX_AI_CHAT_EMPTY")
    if len(normalized_turn_text) > DCX_AI_CHAT_INITIAL_USER_TURN_MAX_CHARACTERS:
        raise RuntimeError("API_DCX_AI_CHAT_CONTEXT_LIMIT_REACHED")

    normalized_language_code = (preferred_language_code or "en").strip().lower() or "en"
    now_ts_ms = int(time.time() * 1000)
    topic_title = _build_ai_chat_title(normalized_turn_text)
    topic_summary_text = _build_ai_chat_summary(normalized_turn_text)
    topic_scope_text = "Direct AI chat started by the user."
    topic_tags = ["ai-chat"]
    connect = connect_to_database or psycopg2.connect

    try:
        policy_check_result = (check_content_policy or generate_dcx_gemini_user_content_policy_check)(
            content_input={
                "content_id": 0,
                "content_kind": "ai_chat_initial_turn",
                "surface": "dcx_app_ai_chats",
                "channel_type": "app",
                "provider_type": "dcx_app",
                "message_format": "text",
                "message_subject": topic_title,
                "raw_text_content": normalized_turn_text,
            },
            file_inputs=[],
        )
        if _read_policy_check_moderation_status(policy_check_result) == "prohibited":
            raise RuntimeError("API_DCX_AI_CHAT_PROHIBITED")

        ai_response = (generate_ai_response or generate_dcx_gemini_market_topic_chat_response)(
            topic_context={
                "market_topic_id": 0,
                "topic_title": topic_title,
                "topic_summary_text": topic_summary_text,
                "topic_scope_text": topic_scope_text,
                "topic_tags_json": topic_tags,
                "topic_status": "open",
            },
            prior_turns=[],
            user_turn_text=normalized_turn_text,
            preferred_language_code=normalized_language_code,
        )

        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_users
                    WHERE id = %s
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (authenticated_user_id,),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("API_DCX_AI_CHAT_USER_NOT_FOUND")

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_contact_messages (
                        user_id,
                        channel_type,
                        provider_type,
                        message_direction,
                        message_format,
                        raw_text_content,
                        derived_text_content,
                        analysis_summary_text,
                        message_metadata_json,
                        processing_status,
                        derivation_status,
                        visible_to_user,
                        received_at_ts_ms,
                        analysis_status,
                        analysis_model_name,
                        analysis_metadata_json,
                        analysis_completed_at_ts_ms,
                        workflow_classification_status,
                        primary_workflow_kind,
                        contains_market_topic_items,
                        workflow_reason_summary,
                        workflow_completed_at_ts_ms
                    )
                    VALUES (
                        %s, 'app', 'dcx_app', 'inbound', 'text', %s, %s, %s, %s::jsonb,
                        'ready', 'completed', FALSE, %s, 'completed', %s, %s::jsonb, %s,
                        'completed', 'market_topic', TRUE, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        authenticated_user_id,
                        normalized_turn_text,
                        normalized_turn_text,
                        topic_summary_text,
                        Json(
                            {
                                "source_surface": "ai_chats",
                                "direct_ai_chat": True,
                                "language_code": normalized_language_code,
                            }
                        ),
                        now_ts_ms,
                        ai_response.get("model_name", ""),
                        Json(
                            {
                                "moderation_status": _read_policy_check_moderation_status(policy_check_result),
                                "policy_check_metadata_json": _build_content_policy_metadata(policy_check_result),
                                "direct_ai_chat": True,
                            }
                        ),
                        now_ts_ms,
                        "Direct AI chat created from explicit user intent.",
                        now_ts_ms,
                    ),
                )
                source_message_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_message_workflow_items (
                        message_id,
                        item_index,
                        item_kind,
                        item_status,
                        item_title,
                        item_summary_text,
                        source_excerpt_text,
                        referenced_attachment_ids_json,
                        confidence_label,
                        workflow_item_metadata_json,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, 1, 'market_topic', 'projected', %s, %s, %s, '[]'::jsonb, 'high', %s::jsonb, %s, %s)
                    RETURNING id
                    """,
                    (
                        source_message_id,
                        topic_title,
                        topic_summary_text,
                        normalized_turn_text,
                        Json(
                            {
                                "source_surface": "ai_chats",
                                "direct_ai_chat": True,
                            }
                        ),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                source_workflow_item_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_market_topics (
                        source_message_id,
                        source_workflow_item_id,
                        initiating_user_id,
                        initiating_contact_method_id,
                        topic_status,
                        topic_title,
                        topic_summary_text,
                        topic_scope_text,
                        topic_tags_json,
                        topic_metadata_json,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, %s, %s, NULL, 'open', %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                    RETURNING id
                    """,
                    (
                        source_message_id,
                        source_workflow_item_id,
                        authenticated_user_id,
                        topic_title,
                        topic_summary_text,
                        topic_scope_text,
                        Json(topic_tags),
                        Json(
                            {
                                "source_surface": "ai_chats",
                                "direct_ai_chat": True,
                                "provider_name": ai_response.get("provider_name", ""),
                                "model_name": ai_response.get("model_name", ""),
                                "prompt_version": ai_response.get("prompt_version", ""),
                                "grounding_metadata": ai_response.get("grounding_metadata", {}),
                            }
                        ),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                market_topic_id = cursor.fetchone()[0]

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
                    VALUES
                        (%s, 'user', %s, %s, %s::jsonb, %s, %s),
                        (%s, 'assistant', %s, %s, %s::jsonb, %s, %s)
                    """,
                    (
                        market_topic_id,
                        source_message_id,
                        normalized_turn_text,
                        Json(
                            {
                                "source_surface": "ai_chats",
                                "source_channel_type": "app",
                                "language_code": normalized_language_code,
                                "direct_ai_chat": True,
                            }
                        ),
                        now_ts_ms,
                        now_ts_ms,
                        market_topic_id,
                        source_message_id,
                        str(ai_response.get("assistant_turn_text") or "").strip(),
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
                                "direct_ai_chat": True,
                            }
                        ),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )

                cursor.execute(
                    """
                    UPDATE stephen_dcx_contact_messages
                    SET workflow_metadata_json = %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        Json(
                            {
                                "workflow_items": [
                                    {
                                        "workflow_item_id": source_workflow_item_id,
                                        "item_kind": "market_topic",
                                        "item_title": topic_title,
                                        "item_summary": topic_summary_text,
                                        "source_excerpt_text": normalized_turn_text,
                                        "referenced_attachment_ids": [],
                                        "confidence_label": "high",
                                    }
                                ],
                                "market_topic_id": market_topic_id,
                                "direct_ai_chat": True,
                            }
                        ),
                        source_message_id,
                    ),
                )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_AI_CHAT_CREATE_FAILED") from exc

    _record_ai_chat_usage_best_effort(
        authenticated_user_id=authenticated_user_id,
        market_topic_id=market_topic_id,
        ai_response=ai_response,
        policy_check_result=policy_check_result,
        connect=connect,
    )

    return {
        "market_topic_id": market_topic_id,
        "source_message_id": source_message_id,
        "source_workflow_item_id": source_workflow_item_id,
        "created_at_ts_ms": now_ts_ms,
    }


def _build_ai_chat_title(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), text.strip())
    collapsed = " ".join(first_line.split())
    if len(collapsed) <= 90:
        return collapsed or "AI chat"
    return f"{collapsed[:87].rstrip()}..."


def _build_ai_chat_summary(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= 240:
        return collapsed
    return f"{collapsed[:237].rstrip()}..."


def _read_policy_check_moderation_status(policy_check_result: dict) -> str:
    normalized_status = str(policy_check_result.get("moderation_status") or "").strip().lower()
    if normalized_status in {"allowed", "prohibited", "not_reviewed"}:
        return normalized_status
    return "not_reviewed"


def _build_content_policy_metadata(policy_check_result: dict) -> dict:
    return {
        "provider_name": policy_check_result.get("provider_name", ""),
        "model_name": policy_check_result.get("model_name", ""),
        "prompt_version": policy_check_result.get("prompt_version", ""),
        "analysis_mode": policy_check_result.get("analysis_mode", ""),
        "policy_check_status": policy_check_result.get("policy_check_status", ""),
        "moderation_status": policy_check_result.get("moderation_status", ""),
        "matched_prohibited_categories": policy_check_result.get("matched_prohibited_categories", []),
        "should_redact_original": policy_check_result.get("should_redact_original") is True,
    }


def _record_ai_chat_usage_best_effort(
    authenticated_user_id: int,
    market_topic_id: int,
    ai_response: dict,
    policy_check_result: dict,
    connect: Callable[..., Any],
) -> None:
    try:
        if policy_check_result.get("policy_check_status") == "completed":
            record_dcx_user_llm_usage_event(
                authenticated_user_id=authenticated_user_id,
                provider_name=str(policy_check_result.get("provider_name") or ""),
                model_name=str(policy_check_result.get("model_name") or ""),
                prompt_version=str(policy_check_result.get("prompt_version") or ""),
                usage_source_kind="content_policy_check",
                usage_source_id=market_topic_id,
                usage_metadata=policy_check_result.get("usage_metadata")
                if isinstance(policy_check_result.get("usage_metadata"), dict)
                else {},
                connect_to_database=connect,
            )
        record_dcx_user_llm_usage_event(
            authenticated_user_id=authenticated_user_id,
            provider_name=ai_response.get("provider_name", ""),
            model_name=ai_response.get("model_name", ""),
            prompt_version=ai_response.get("prompt_version", ""),
            usage_source_kind="ai_chat_initial",
            usage_source_id=market_topic_id,
            usage_metadata=ai_response.get("usage_metadata")
            if isinstance(ai_response.get("usage_metadata"), dict)
            else {},
            connect_to_database=connect,
        )
        record_dcx_user_activity_event(
            user_id=authenticated_user_id,
            activity_kind="ai_chat_created",
            surface="app",
            entity_kind="market_topic",
            entity_id=market_topic_id,
            activity_summary="AI chat created.",
            activity_metadata={"direct_ai_chat": True},
            connect_to_database=connect,
        )
    except RuntimeError:
        pass
