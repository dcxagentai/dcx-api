"""
CONTEXT:
This file calls Google Gemini for one structured DCX market-topic seed.
It exists so Slice 1 can turn one routed market topic into the first AI-ready topic object and
opening assistant response for the later trader-to-AI topic lane.
"""

from __future__ import annotations

import json
import os
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

PROMPT_VERSION_DCX_MARKET_TOPIC_SEED = "dcx_market_topic_seed_2026_04_28_v1"


def generate_dcx_gemini_structured_market_topic_seed(
    message_input: dict,
    workflow_item: dict,
    attachment_inputs: list[dict],
    send_gemini_request: Callable[[dict], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - message_input describes one persisted DCX contact message already analysed once.
        - workflow_item describes one identified market-topic workflow item from that message.
        - attachment_inputs contains already-analysed attachment summaries relevant to the source message.
        - GEMINI_API_KEY is configured unless send_gemini_request is injected by tests.
      postconditions:
        - Returns one normalized market-topic seed payload with metadata and one opening AI response.
      side_effects:
        - may call Google Gemini over HTTPS
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: market_topic_seed:{message_id}:{workflow_item_index}:{PROMPT_VERSION_DCX_MARKET_TOPIC_SEED}
      locks: []
      contention_strategy: caller owns projection-item locking

    NARRATIVE:
      WHY this exists:
        - DCX market-topic items should not stop as dead labels; they should already look like the start
          of a useful trader-to-AI topic thread.
      WHEN TO USE it:
        - Use it after Prompt 1 has identified one market-topic workflow item.
      WHEN NOT TO USE it:
        - Do not use it for final trade extraction or moderation.
      WHAT CAN GO WRONG:
        - Gemini can fail or return malformed output.
      WHAT COMES NEXT:
        - Slice 2 can append later user and assistant turns to the same seeded topic thread.

    TESTS:
      - to be added with first topic-seed smoke coverage

    ERRORS:
      - API_DCX_GEMINI_MARKET_TOPIC_SEED_FAILED:
          suggested_action: Retry after confirming Gemini credentials and provider health.
          common_causes:
            - missing GEMINI_API_KEY
            - malformed model output
            - transient provider failure
          recovery_steps:
            - Verify GEMINI_API_KEY and GEMINI_MESSAGE_ANALYSIS_MODEL.
            - Retry after provider health is restored.
          retry_safe: true

    CODE:
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = read_dcx_gemini_message_analysis_model_name()

    if api_key == "" and send_gemini_request is None:
        raise RuntimeError("API_DCX_GEMINI_MARKET_TOPIC_SEED_FAILED")

    request_context = {
        "api_key": api_key,
        "model_name": model_name,
        "prompt_text": _build_dcx_market_topic_seed_prompt(
            message_input=message_input,
            workflow_item=workflow_item,
            attachment_inputs=attachment_inputs,
        ),
        "system_instruction": build_dcx_gemini_market_topic_system_instruction(),
        "google_search_enabled": True,
        "response_schema": _build_dcx_market_topic_seed_response_schema(),
    }

    try:
        response_payload = (send_gemini_request or _send_gemini_generate_content_request)(request_context)
        output_text = str(response_payload.get("output_text", "")).strip()
        parsed_output = json.loads(output_text)
        usage_metadata = response_payload.get("usage_metadata") if isinstance(response_payload, dict) else {}
    except Exception as exc:
        raise RuntimeError("API_DCX_GEMINI_MARKET_TOPIC_SEED_FAILED") from exc

    return _normalize_market_topic_seed_output(
        parsed_output=parsed_output,
        model_name=model_name,
        grounding_metadata=normalize_dcx_gemini_grounding_metadata(response_payload.get("grounding_metadata")),
        usage_metadata=usage_metadata if isinstance(usage_metadata, dict) else {},
    )


def _send_gemini_generate_content_request(request_context: dict) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=request_context["api_key"])
    response = client.models.generate_content(
        model=request_context["model_name"],
        contents=[request_context["prompt_text"]],
        config=types.GenerateContentConfig(
            system_instruction=request_context["system_instruction"],
            response_mime_type="application/json",
            response_schema=request_context["response_schema"],
            tools=[
                types.Tool(google_search=types.GoogleSearch()),
            ],
        ),
    )
    return {
        "output_text": (response.text or "").strip(),
        "grounding_metadata": read_dcx_gemini_response_grounding_metadata(response),
        "usage_metadata": read_dcx_gemini_usage_metadata(response),
    }


def _build_dcx_market_topic_seed_prompt(
    message_input: dict,
    workflow_item: dict,
    attachment_inputs: list[dict],
) -> str:
    attachment_manifest_lines = [
        (
            f"- attachment_id={attachment_input['attachment_id']}"
            f" file_kind={attachment_input['file_kind']}"
            f" filename=\"{attachment_input['original_filename']}\""
            f" summary=\"{attachment_input['analysis_summary_text']}\""
            f" context=\"{attachment_input['context_within_message']}\""
        )
        for attachment_input in attachment_inputs
    ]
    return f"""
<task>
- Formulate the first reply to the user's message or question.
- Write a concise topic title.
- Write a practical topic summary.
- Write a topic_scope_text as a concise boundary for what this topic chat is about.
- Suggest useful tags or themes for later filtering.
- Write one opening_ai_response_text:
    - grounded
    - approx 100 words unless it obviously needs to be longer or shorter
- Return JSON only.
</task>

<message>
message_id={message_input.get("message_id")}
channel_type={message_input.get("channel_type")}
provider_type={message_input.get("provider_type")}
message_subject={message_input.get("message_subject")}
message_summary={message_input.get("analysis_summary_text")}
message_synthesis={message_input.get("derived_text_content")}
raw_text={message_input.get("raw_text_content")}
</message>

<workflow_item>
item_kind={workflow_item.get("item_kind")}
item_title={workflow_item.get("item_title")}
item_summary={workflow_item.get("item_summary")}
source_excerpt_text={workflow_item.get("source_excerpt_text")}
</workflow_item>

<attachment_context>
{chr(10).join(attachment_manifest_lines) if attachment_manifest_lines else "- none"}
</attachment_context>
""".strip()


def _build_dcx_market_topic_seed_response_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "topic_title": {"type": "string"},
            "topic_summary_text": {"type": "string"},
            "topic_scope_text": {"type": "string"},
            "topic_tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "opening_ai_response_text": {"type": "string"},
        },
        "required": [
            "topic_title",
            "topic_summary_text",
            "topic_scope_text",
            "topic_tags",
            "opening_ai_response_text",
        ],
    }


def _normalize_market_topic_seed_output(
    parsed_output: dict,
    model_name: str,
    grounding_metadata: dict,
    usage_metadata: dict | None = None,
) -> dict:
    opening_ai_response_text = str(parsed_output.get("opening_ai_response_text") or "").strip()
    return {
        "model_name": model_name,
        "provider_name": "google_gemini",
        "prompt_version": PROMPT_VERSION_DCX_MARKET_TOPIC_SEED,
        "usage_metadata": usage_metadata if isinstance(usage_metadata, dict) else {},
        "topic_title": str(parsed_output.get("topic_title") or "").strip(),
        "topic_summary_text": str(parsed_output.get("topic_summary_text") or "").strip(),
        "topic_scope_text": str(parsed_output.get("topic_scope_text") or "").strip(),
        "topic_tags": _normalize_string_list(parsed_output.get("topic_tags")),
        "opening_ai_response_text": append_dcx_grounding_sources_to_assistant_text(
            assistant_turn_text=opening_ai_response_text,
            grounding_metadata=grounding_metadata,
        ),
        "grounding_metadata": grounding_metadata,
        "raw_output_json": parsed_output,
    }


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized_values: list[str] = []
    for item in value:
        normalized_item = str(item or "").strip()
        if normalized_item != "" and normalized_item not in normalized_values:
            normalized_values.append(normalized_item)
    return normalized_values
