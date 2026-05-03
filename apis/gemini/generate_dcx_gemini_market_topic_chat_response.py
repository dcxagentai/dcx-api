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
  - No dedicated unit test exists yet; smoke through POST /users/me/market-topics/{id}/turns.

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
import os
from typing import Any, Callable

from apis.gemini.build_dcx_gemini_market_topic_system_instruction import (
    build_dcx_gemini_market_topic_system_instruction,
)
from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)

PROMPT_VERSION_DCX_MARKET_TOPIC_CHAT = "dcx_market_topic_chat_2026_05_01_v1"


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
    google_search_enabled = True
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

    try:
        response_payload = (send_gemini_request or _send_gemini_generate_content_request)(request_context)
        assistant_turn_text = str(response_payload.get("output_text", "")).strip()
    except Exception as exc:
        raise RuntimeError("API_DCX_GEMINI_MARKET_TOPIC_CHAT_FAILED") from exc

    if assistant_turn_text == "":
        raise RuntimeError("API_DCX_GEMINI_MARKET_TOPIC_CHAT_FAILED")

    grounding_metadata = _normalize_dcx_gemini_grounding_metadata(response_payload.get("grounding_metadata"))
    assistant_turn_text = _append_dcx_grounding_sources_to_assistant_text(
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


def _send_gemini_generate_content_request(request_context: dict) -> dict:
    from google import genai
    from google.genai import types

    config_kwargs: dict[str, Any] = {
        "system_instruction": request_context["system_instruction"],
    }
    config_kwargs["tools"] = [
        types.Tool(google_search=types.GoogleSearch()),
    ]

    client = genai.Client(api_key=request_context["api_key"])
    response = client.models.generate_content(
        model=request_context["model_name"],
        contents=_build_gemini_content_objects(request_context["contents"], types),
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return {
        "output_text": (response.text or "").strip(),
        "grounding_metadata": _read_dcx_gemini_response_grounding_metadata(response),
    }


def _build_market_topic_chat_contents(
    topic_context: dict,
    prior_turns: list[dict],
    user_turn_text: str,
    preferred_language_code: str,
    google_search_enabled: bool,
) -> list[dict]:
    search_instruction = (
        "\n- Google Search is available. Use it only when the latest user input asks for current, latest, recent, time-sensitive, or source-sensitive facts."
        "\n- Prefer a concise synthesis of the most relevant recent reports over a long article list when search is useful."
    )
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
{search_instruction}
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


def _read_dcx_gemini_response_grounding_metadata(response: Any) -> dict:
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return {}
    grounding_metadata = getattr(candidates[0], "grounding_metadata", None)
    return _model_dump_or_dict(grounding_metadata)


def _normalize_dcx_gemini_grounding_metadata(value: Any) -> dict:
    metadata = _model_dump_or_dict(value)
    if not metadata:
        return {}

    search_queries = _normalize_string_list(
        metadata.get("web_search_queries")
        or metadata.get("webSearchQueries")
        or []
    )
    grounding_chunks = metadata.get("grounding_chunks") or metadata.get("groundingChunks") or []
    sources = []
    seen_uris = set()
    if isinstance(grounding_chunks, list):
        for chunk in grounding_chunks:
            chunk_dict = _model_dump_or_dict(chunk)
            web_dict = _model_dump_or_dict(chunk_dict.get("web"))
            uri = str(web_dict.get("uri") or "").strip()
            title = str(web_dict.get("title") or "").strip()
            if uri == "" or uri in seen_uris:
                continue
            seen_uris.add(uri)
            sources.append(
                {
                    "title": title,
                    "uri": uri,
                }
            )
            if len(sources) >= 4:
                break

    normalized_metadata = {
        "web_search_queries": search_queries,
        "sources": sources,
    }
    return normalized_metadata if search_queries or sources else {}


def _append_dcx_grounding_sources_to_assistant_text(assistant_turn_text: str, grounding_metadata: dict) -> str:
    sources = grounding_metadata.get("sources") if isinstance(grounding_metadata, dict) else []
    if not isinstance(sources, list) or not sources:
        return assistant_turn_text
    if "sources:" in assistant_turn_text.lower():
        return assistant_turn_text

    source_lines = []
    for source in sources[:3]:
        source_dict = _model_dump_or_dict(source)
        title = str(source_dict.get("title") or "").strip()
        uri = str(source_dict.get("uri") or "").strip()
        if uri == "":
            continue
        source_lines.append(f"- [{title}]({uri})" if title else f"- {uri}")
    if not source_lines:
        return assistant_turn_text
    return f"{assistant_turn_text.strip()}\n\nSources:\n{chr(10).join(source_lines)}"


def _model_dump_or_dict(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(exclude_none=True)
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized_items = []
    for item in value:
        normalized_item = str(item or "").strip()
        if normalized_item and normalized_item not in normalized_items:
            normalized_items.append(normalized_item)
    return normalized_items
