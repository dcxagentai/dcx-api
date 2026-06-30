"""
CONTEXT:
This file calls Google Gemini for one private DCX trader-to-AI market-topic chat reply.
It exists so an existing structured market topic can become a basic ongoing AI conversation
without adding any new provider plumbing for the MVP.

FLOW/SYSTEM:
- Private app Topics detail.
- A trader owns one market topic.
- The app appends a user turn, asks Gemini for the next assistant turn using the topic and
  previous turns as context, and stores the assistant turn.

CONTRACT:
  preconditions:
    - topic_context describes one authenticated-user-owned DCX market topic.
    - prior_turns are ordered oldest to newest and belong to the same market topic.
    - user_turn_text is a non-empty trader message.
    - GEMINI_API_KEY and GEMINI_MESSAGE_ANALYSIS_MODEL are configured unless send_gemini_request is injected.
  postconditions:
    - Returns one concise assistant reply string.
    - Does not mutate database state.
  side_effects:
    - may call Google Gemini over HTTPS
  idempotent: true
  retry_safe: true
  async: false
  idempotency_key: market_topic_chat_response:{market_topic_id}:{turn_count}:{user_turn_text_hash}
  locks: []
  contention_strategy: caller owns topic authorization and persistence ordering

NARRATIVE:
  WHY this exists:
    - DCX already creates market topics and an opening AI response. This file lets the trader
      continue that private topic as a basic AI chat while keeping all provider-specific code
      in the Gemini boundary.
  WHEN TO USE it:
    - Use it when an authenticated trader posts a new message in their own market-topic AI chat.
  WHEN NOT TO USE it:
    - Do not use it for public forum comments, trade-counterparty chats, or content moderation.
  WHAT CAN GO WRONG:
    - Gemini credentials may be missing, the provider may fail, or the model may return an empty reply.
  WHAT COMES NEXT:
    - Later slices can add compaction, provider choice, stricter moderation, and translated response variants.

TESTS:
  - No dedicated unit test exists yet; smoke through POST /ai/chats/{id}/turns.

ERRORS:
  - API_DCX_GEMINI_MARKET_TOPIC_CHAT_FAILED:
      suggested_action: Retry after confirming Gemini credentials and provider health.
      common_causes:
        - missing GEMINI_API_KEY
        - missing GEMINI_MESSAGE_ANALYSIS_MODEL
        - transient provider failure
        - empty model response
      recovery_steps:
        - Verify GEMINI_API_KEY and GEMINI_MESSAGE_ANALYSIS_MODEL.
        - Retry once provider health is restored.
      retry_safe: true

CODE:
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Callable

from apis.gemini.build_dcx_gemini_market_topic_system_instruction import (
    build_dcx_gemini_market_topic_system_instruction,
)
from apis.gemini.format_dcx_gemini_grounding_metadata import (
    append_dcx_grounding_sources_to_assistant_text,
    normalize_dcx_gemini_grounding_metadata,
    read_dcx_gemini_response_grounding_metadata,
)
from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)
from apis.gemini.read_dcx_gemini_usage_metadata import read_dcx_gemini_usage_metadata

PROMPT_VERSION_DCX_MARKET_TOPIC_CHAT = "dcx_market_topic_chat_2026_05_01_v1"
LOGGER = logging.getLogger(__name__)

DCX_MARKET_TOPIC_CHAT_SEARCH_TRIGGER_TERMS = (
    "as of",
    "breaking",
    "current",
    "currently",
    "latest",
    "last few",
    "last week",
    "last month",
    "news",
    "now",
    "past few",
    "recent",
    "recently",
    "right now",
    "this morning",
    "this week",
    "this month",
    "today",
    "tonight",
    "update",
    "updated",
    "yesterday",
)


def generate_dcx_gemini_market_topic_chat_response(
    topic_context: dict,
    prior_turns: list[dict],
    user_turn_text: str,
    preferred_language_code: str = "en",
    send_gemini_request: Callable[[dict], dict] | None = None,
) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = read_dcx_gemini_message_analysis_model_name()

    if api_key == "" and send_gemini_request is None:
        raise RuntimeError("API_DCX_GEMINI_MARKET_TOPIC_CHAT_FAILED")

    system_instruction = build_dcx_gemini_market_topic_system_instruction()
    preferred_google_search_enabled = _should_enable_google_search_for_market_topic_chat(
        topic_context=topic_context,
        user_turn_text=user_turn_text,
    )
    try:
        response_payload, assistant_turn_text, usage_metadata, google_search_enabled, contents = (
            _run_market_topic_chat_request(
                api_key=api_key,
                model_name=model_name,
                system_instruction=system_instruction,
                topic_context=topic_context,
                prior_turns=prior_turns,
                user_turn_text=user_turn_text,
                preferred_language_code=preferred_language_code,
                google_search_enabled=preferred_google_search_enabled,
                send_gemini_request=send_gemini_request,
            )
        )
    except Exception as exc:
        if not preferred_google_search_enabled:
            LOGGER.exception("Gemini market-topic chat failed without Google Search.")
            raise RuntimeError("API_DCX_GEMINI_MARKET_TOPIC_CHAT_FAILED") from exc
        LOGGER.warning(
            "Gemini market-topic chat failed with Google Search enabled; retrying without Google Search.",
            exc_info=True,
        )
        try:
            response_payload, assistant_turn_text, usage_metadata, google_search_enabled, contents = (
                _run_market_topic_chat_request(
                    api_key=api_key,
                    model_name=model_name,
                    system_instruction=system_instruction,
                    topic_context=topic_context,
                    prior_turns=prior_turns,
                    user_turn_text=user_turn_text,
                    preferred_language_code=preferred_language_code,
                    google_search_enabled=False,
                    send_gemini_request=send_gemini_request,
                )
            )
        except Exception as fallback_exc:
            LOGGER.exception("Gemini market-topic chat failed after Google Search fallback.")
            raise RuntimeError("API_DCX_GEMINI_MARKET_TOPIC_CHAT_FAILED") from fallback_exc

    grounding_metadata = normalize_dcx_gemini_grounding_metadata(response_payload.get("grounding_metadata"))
    assistant_turn_text = append_dcx_grounding_sources_to_assistant_text(
        assistant_turn_text=assistant_turn_text,
        grounding_metadata=grounding_metadata,
    )

    return {
        "assistant_turn_text": assistant_turn_text,
        "model_name": model_name,
        "provider_name": "google_gemini",
        "prompt_version": PROMPT_VERSION_DCX_MARKET_TOPIC_CHAT,
        "google_search_enabled": google_search_enabled,
        "grounding_metadata": grounding_metadata,
        "usage_metadata": usage_metadata if isinstance(usage_metadata, dict) else {},
        "prompt_fingerprint": hashlib.sha256(
            json.dumps(
                {
                    "system_instruction": system_instruction,
                    "contents": contents,
                    "google_search_enabled": google_search_enabled,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
    }


def _run_market_topic_chat_request(
    api_key: str,
    model_name: str,
    system_instruction: str,
    topic_context: dict,
    prior_turns: list[dict],
    user_turn_text: str,
    preferred_language_code: str,
    google_search_enabled: bool,
    send_gemini_request: Callable[[dict], dict] | None,
) -> tuple[dict, str, dict, bool, list[dict]]:
    contents = _build_market_topic_chat_contents(
        topic_context=topic_context,
        prior_turns=prior_turns,
        user_turn_text=user_turn_text,
        preferred_language_code=preferred_language_code,
        google_search_enabled=google_search_enabled,
    )
    request_context = {
        "api_key": api_key,
        "model_name": model_name,
        "system_instruction": system_instruction,
        "contents": contents,
        "google_search_enabled": google_search_enabled,
    }
    response_payload = (send_gemini_request or _send_gemini_generate_content_request)(request_context)
    assistant_turn_text = str(response_payload.get("output_text", "")).strip()
    usage_metadata = response_payload.get("usage_metadata") if isinstance(response_payload, dict) else {}
    if assistant_turn_text == "":
        raise RuntimeError("API_DCX_GEMINI_MARKET_TOPIC_CHAT_EMPTY_RESPONSE")
    return (
        response_payload,
        assistant_turn_text,
        usage_metadata if isinstance(usage_metadata, dict) else {},
        google_search_enabled,
        contents,
    )


def _send_gemini_generate_content_request(request_context: dict) -> dict:
    from google import genai
    from google.genai import types

    config_kwargs: dict[str, Any] = {
        "system_instruction": request_context["system_instruction"],
    }
    if request_context.get("google_search_enabled") is True:
        config_kwargs["tools"] = [
            types.Tool(google_search=types.GoogleSearch()),
        ]

    client = genai.Client(api_key=request_context["api_key"])
    response = _generate_content_with_brief_retries(
        generate_content=lambda: client.models.generate_content(
            model=request_context["model_name"],
            contents=_build_gemini_content_objects(request_context["contents"], types),
            config=types.GenerateContentConfig(**config_kwargs),
        ),
        retry_enabled=request_context.get("google_search_enabled") is not True,
    )
    return {
        "output_text": (response.text or "").strip(),
        "grounding_metadata": read_dcx_gemini_response_grounding_metadata(response),
        "usage_metadata": read_dcx_gemini_usage_metadata(response),
    }


def _build_market_topic_chat_contents(
    topic_context: dict,
    prior_turns: list[dict],
    user_turn_text: str,
    preferred_language_code: str,
    google_search_enabled: bool,
) -> list[dict]:
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "text": f"""
<task>
- You are chatting to a user about this topic.
- Continue the chat with your next response.
- Formulate your next reply.
- Reply in the language of the latest user input.
- {read_dcx_market_topic_chat_search_instruction(google_search_enabled)}
</task>

<topic>
market_topic_id={topic_context.get("market_topic_id")}
title={topic_context.get("topic_title")}
summary={topic_context.get("topic_summary_text")}
scope={topic_context.get("topic_scope_text")}
tags={", ".join(topic_context.get("topic_tags_json") or [])}
</topic>
""".strip()
                }
            ],
        }
    ]
    for turn in prior_turns:
        role = str(turn.get("turn_role") or "user").strip().lower()
        turn_text = str(turn.get("turn_text") or "").strip()
        if turn_text:
            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": turn_text}],
                }
            )

    contents.append(
        {
            "role": "user",
            "parts": [{"text": user_turn_text}],
        }
    )
    return contents


def _generate_content_with_brief_retries(
    generate_content: Callable[[], Any],
    retry_enabled: bool,
) -> Any:
    last_exception: Exception | None = None
    attempt_count = 3 if retry_enabled else 1
    for attempt_index in range(attempt_count):
        try:
            return generate_content()
        except Exception as exc:
            last_exception = exc
            if attempt_index >= attempt_count - 1 or not _is_retryable_gemini_exception(exc):
                raise
            time.sleep(0.75 * (attempt_index + 1))
    raise last_exception or RuntimeError("API_DCX_GEMINI_MARKET_TOPIC_CHAT_FAILED")


def _is_retryable_gemini_exception(exc: Exception) -> bool:
    normalized_message = str(exc).lower()
    return any(
        retryable_fragment in normalized_message
        for retryable_fragment in (
            "429",
            "503",
            "too many requests",
            "resource_exhausted",
            "unavailable",
        )
    )


def _should_enable_google_search_for_market_topic_chat(
    topic_context: dict,
    user_turn_text: str,
) -> bool:
    combined_text = " ".join(
        [
            str(user_turn_text or ""),
            str(topic_context.get("topic_title") or ""),
            " ".join(str(tag) for tag in (topic_context.get("topic_tags_json") or [])),
        ]
    ).lower()
    return any(search_term in combined_text for search_term in DCX_MARKET_TOPIC_CHAT_SEARCH_TRIGGER_TERMS)


def read_dcx_market_topic_chat_search_instruction(google_search_enabled: bool) -> str:
    if google_search_enabled:
        return "Google Search is available for this response; use it only if current, recent, or source-sensitive facts are needed."
    return "Google Search is not enabled for this response; answer from the conversation context and your general knowledge."


def _build_gemini_content_objects(contents: list[dict], types: Any) -> list[Any]:
    content_objects = []
    for content in contents:
        role = str(content.get("role") or "user").strip().lower()
        part_objects = [
            types.Part(text=str(part.get("text") or ""))
            for part in content.get("parts", [])
            if str(part.get("text") or "").strip() != ""
        ]
        if part_objects:
            content_objects.append(types.Content(role=role, parts=part_objects))
    return content_objects
