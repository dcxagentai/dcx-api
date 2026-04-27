"""
CONTEXT:
This file derives normalized analyzable text, a short synthesis, and one detected language code
from one raw DCX contact message.
It exists so the first app-originated message flow can persist one stable derivation result before
broader trade or question classification is introduced.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

import httpx


def derive_dcx_contact_message_text_and_language_with_llm(
    raw_text_content: str,
    send_openai_request: Callable[[dict], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - raw_text_content is one inbound message text payload, possibly noisy or multilingual.
      postconditions:
        - Returns one normalized derivation payload with derived text, one short analysis summary,
          one detected language code when possible, and one derivation mode label.
        - Falls back to a deterministic non-LLM projection when the OpenAI API key is not configured.
      side_effects:
        - may call the OpenAI Responses API over HTTPS
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: null
      locks: []
      contention_strategy: none; this function is pure with respect to local state

    NARRATIVE:
      WHY this exists:
        - The first messages slice needs one derivation step that turns raw user text into a more
          stable textual artifact we can store and render immediately.
      WHEN TO USE it:
        - Use it after one inbound message row has been persisted and before that row is marked ready.
      WHEN NOT TO USE it:
        - Do not use it yet for final business intent classification.
        - Do not use it as a replacement for OCR, transcription, or richer multimodal tooling later.
      WHAT CAN GO WRONG:
        - The OpenAI API may be unavailable or misconfigured.
        - The model can return malformed JSON.
        - An empty string may not warrant model usage.
      WHAT COMES NEXT:
        - Later message-processing stages can branch from this normalized text into trade, question,
          reply-context, or noise classification.

    TESTS:
      - returns_fallback_derivation_when_openai_api_key_is_missing
      - returns_structured_derivation_from_openai_response_payload

    ERRORS:
      - API_DCX_CONTACT_MESSAGE_DERIVATION_FAILED:
          suggested_action: Retry the derivation after confirming the model provider is healthy.
          common_causes:
            - provider outage
            - invalid OpenAI configuration
            - malformed model output
          recovery_steps:
            - Verify OPENAI_API_KEY and the configured model name.
            - Retry after provider health is restored.
          retry_safe: true

    CODE:
    """
    normalized_raw_text = raw_text_content.strip()
    if normalized_raw_text == "":
        return {
            "derived_text_content": "",
            "analysis_summary_text": "No message text was available for derivation.",
            "detected_language_code": None,
            "derivation_mode": "empty_input",
            "model_name": "",
        }

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model_name = os.getenv("DCX_OPENAI_MESSAGE_DERIVATION_MODEL", "gpt-5.2").strip() or "gpt-5.2"
    if openai_api_key == "":
        return {
            "derived_text_content": normalized_raw_text,
            "analysis_summary_text": (
                "Stored raw text directly because no derivation model is configured in this environment."
            ),
            "detected_language_code": None,
            "derivation_mode": "fallback_no_model",
            "model_name": "",
        }

    request_payload = {
        "model": model_name,
        "instructions": (
            "You normalize one inbound user message for later workflow routing. "
            "Return JSON only. Keep the user's meaning. Do not classify business intent yet."
        ),
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Read this inbound user message and return JSON with: "
                            "`derived_text_content`, `analysis_summary_text`, and "
                            "`detected_language_code`. "
                            "`derived_text_content` should preserve the meaning in clear text. "
                            "`analysis_summary_text` should be a short one- or two-sentence plain-English summary. "
                            "`detected_language_code` should be an ISO language code like `en`, `es`, `fr`, `de`, or null if unclear.\n\n"
                            f"Message:\n{normalized_raw_text}"
                        ),
                    }
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "dcx_contact_message_derivation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "derived_text_content": {"type": "string"},
                        "analysis_summary_text": {"type": "string"},
                        "detected_language_code": {
                            "type": ["string", "null"],
                            "minLength": 2,
                            "maxLength": 12,
                        },
                    },
                    "required": [
                        "derived_text_content",
                        "analysis_summary_text",
                        "detected_language_code",
                    ],
                    "additionalProperties": False,
                },
            }
        },
    }

    try:
        response_payload = (send_openai_request or _send_openai_responses_api_request)(
            {
                "openai_api_key": openai_api_key,
                "request_payload": request_payload,
            }
        )
        output_text = _read_output_text_from_openai_response(response_payload)
        parsed_output = json.loads(output_text)
    except Exception as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_DERIVATION_FAILED") from exc

    derived_text_content = str(parsed_output.get("derived_text_content", "")).strip()
    analysis_summary_text = str(parsed_output.get("analysis_summary_text", "")).strip()
    detected_language_code_raw = parsed_output.get("detected_language_code")
    detected_language_code = None
    if isinstance(detected_language_code_raw, str) and detected_language_code_raw.strip() != "":
        detected_language_code = detected_language_code_raw.strip().lower()

    if derived_text_content == "":
        derived_text_content = normalized_raw_text

    if analysis_summary_text == "":
        analysis_summary_text = "Derived text stored from the inbound message."

    return {
        "derived_text_content": derived_text_content,
        "analysis_summary_text": analysis_summary_text,
        "detected_language_code": detected_language_code,
        "derivation_mode": "openai_responses_api",
        "model_name": model_name,
    }


def _send_openai_responses_api_request(request_context: dict) -> dict:
    response = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {request_context['openai_api_key']}",
            "Content-Type": "application/json",
        },
        json=request_context["request_payload"],
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def _read_output_text_from_openai_response(response_payload: dict) -> str:
    output_items = response_payload.get("output")
    if not isinstance(output_items, list):
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_DERIVATION_FAILED")

    output_text_parts: list[str] = []
    for output_item in output_items:
        if not isinstance(output_item, dict):
            continue
        content_items = output_item.get("content")
        if not isinstance(content_items, list):
            continue
        for content_item in content_items:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") != "output_text":
                continue
            text_value = content_item.get("text")
            if isinstance(text_value, str) and text_value.strip() != "":
                output_text_parts.append(text_value)

    output_text = "\n".join(output_text_parts).strip()
    if output_text == "":
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_DERIVATION_FAILED")

    return output_text
