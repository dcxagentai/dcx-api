"""
CONTEXT:
This file calls Google Gemini for one reusable DCX user-content policy check.
It exists so app messages, AI chat turns, future feed posts, DMs, and other user inputs can share
one context-aware prohibited-content decision instead of burying that decision inside workflow
classification prompts.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable

from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)
from apis.gemini.read_dcx_gemini_usage_metadata import read_dcx_gemini_usage_metadata

PROMPT_VERSION_DCX_USER_CONTENT_POLICY_CHECK = "dcx_user_content_policy_check_2026_06_25_v1"
LOGGER = logging.getLogger(__name__)
DCX_USER_CONTENT_POLICY_REASON_CODES = (
    "prohibited_children",
    "prohibited_sexually_explicit",
    "prohibited_exploitation_or_trafficking",
    "prohibited_drugs",
    "prohibited_weapons_explosives_conventional",
    "prohibited_weapons_nuclear_chemical",
    "prohibited_extremism_terrorism",
    "prohibited_organised_crime",
    "prohibited_fraud",
    "prohibited_sanctions",
)


def generate_dcx_gemini_user_content_policy_check(
    content_input: dict,
    file_inputs: list[dict] | None = None,
    send_gemini_request: Callable[[dict], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - content_input describes one user-authored DCX input.
        - file_inputs may contain already-stored attachment bytes for multimodal checks.
        - GEMINI_API_KEY is configured unless send_gemini_request is injected by tests.
      postconditions:
        - Returns one normalized moderation decision using DCX's prohibited reason codes.
      side_effects:
        - may call Google Gemini over HTTPS
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: user_content_policy:{content_id}:{PROMPT_VERSION_DCX_USER_CONTENT_POLICY_CHECK}

    ERRORS:
      - API_DCX_GEMINI_USER_CONTENT_POLICY_CHECK_FAILED:
          suggested_action: Retry after confirming Gemini credentials and provider health.
          retry_safe: true
    """
    normalized_content_input = _normalize_content_input(content_input)
    normalized_file_inputs = [_normalize_file_input(file_input) for file_input in (file_inputs or [])]

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = read_dcx_gemini_message_analysis_model_name()

    if api_key == "" and send_gemini_request is None:
        return _build_fallback_policy_check(
            content_input=normalized_content_input,
            model_name="",
            provider_name="google_gemini",
            analysis_mode="fallback_no_model",
        )

    request_context = {
        "api_key": api_key,
        "model_name": model_name,
        "prompt_text": _build_dcx_user_content_policy_check_prompt(
            content_input=normalized_content_input,
            file_inputs=normalized_file_inputs,
        ),
        "file_inputs": normalized_file_inputs,
        "response_schema": _build_dcx_user_content_policy_check_response_schema(),
    }

    try:
        response_payload = (send_gemini_request or _send_gemini_generate_content_request)(request_context)
        output_text = str(response_payload.get("output_text", "")).strip()
        parsed_output = json.loads(output_text)
        usage_metadata = response_payload.get("usage_metadata") if isinstance(response_payload, dict) else {}
    except Exception as exc:
        LOGGER.exception("Gemini user-content policy check failed.")
        raise RuntimeError("API_DCX_GEMINI_USER_CONTENT_POLICY_CHECK_FAILED") from exc

    return _normalize_policy_check_output(
        parsed_output=parsed_output,
        model_name=model_name,
        provider_name="google_gemini",
        analysis_mode="gemini_generate_content",
        usage_metadata=usage_metadata if isinstance(usage_metadata, dict) else {},
    )


def _send_gemini_generate_content_request(request_context: dict) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=request_context["api_key"])
    contents: list[Any] = [request_context["prompt_text"]]
    for file_input in request_context["file_inputs"]:
        contents.append(
            types.Part.from_bytes(
                data=file_input["file_bytes"],
                mime_type=file_input["content_type"],
            )
        )

    response = _generate_content_with_brief_retries(
        generate_content=lambda: client.models.generate_content(
            model=request_context["model_name"],
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=request_context["response_schema"],
            ),
        )
    )
    return {
        "output_text": (response.text or "").strip(),
        "usage_metadata": read_dcx_gemini_usage_metadata(response),
    }


def _generate_content_with_brief_retries(generate_content: Callable[[], Any]) -> Any:
    last_exception: Exception | None = None
    for attempt_index in range(3):
        try:
            return generate_content()
        except Exception as exc:
            last_exception = exc
            if attempt_index >= 2 or not _is_retryable_gemini_exception(exc):
                raise
            time.sleep(0.75 * (attempt_index + 1))
    raise last_exception or RuntimeError("API_DCX_GEMINI_USER_CONTENT_POLICY_CHECK_FAILED")


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


def _build_dcx_user_content_policy_check_prompt(content_input: dict, file_inputs: list[dict]) -> str:
    file_manifest_lines = []
    for file_input in file_inputs:
        file_manifest_lines.append(
            (
                f"<file attachment_id=\"{file_input['attachment_id']}\" "
                f"file_object_id=\"{file_input['file_object_id']}\" "
                f"file_kind=\"{file_input['file_kind']}\" "
                f"content_type=\"{file_input['content_type']}\" "
                f"filename=\"{_escape_prompt_attribute(file_input['original_filename'])}\" />"
            )
        )

    return f"""
<dcx_task>
Classify whether this DCX user input is allowed or prohibited under DCX content policy.
Return JSON only. Do not wrap JSON in markdown.
</dcx_task>

<policy_rules>
- Judge the user's likely intent from context, semantics, and the whole input, not just keywords.
- Return moderation_status = "allowed" when the input is legitimate market, trade, logistics,
  legal, compliance, risk, business, educational, or general discussion.
- Return moderation_status = "prohibited" when the input attempts to buy, sell, source, route,
  procure, conceal, evade controls, operationalize, facilitate, or materially assist prohibited
  activity or prohibited materials.
- Discussion about sanctions, controlled goods, fraud, crime, conflict, or risk as market context,
  compliance context, legal context, news context, or defensive risk analysis can be allowed.
- Attempts to evade sanctions, source sanctioned goods, route around controls, falsify documents,
  conceal beneficial ownership, or help illegal procurement are prohibited.
- Refuse sexually explicit material, pornography, and any abuse, exploitation, sexualization,
  or manipulation of children.
- If moderation_status = "prohibited":
    - include every matching prohibited category code in matched_prohibited_categories;
    - include a short internal moderation_reason_summary explaining what triggered the block;
    - set should_redact_original = true;
    - write a short user_facing_message that says the input was blocked by DCX policy.
- If moderation_status = "allowed":
    - matched_prohibited_categories = [];
    - moderation_reason_summary = "";
    - should_redact_original = false;
    - user_facing_message = "".
</policy_rules>

<prohibited_categories>
- prohibited_children
- prohibited_sexually_explicit
- prohibited_exploitation_or_trafficking
- prohibited_drugs
- prohibited_weapons_explosives_conventional
- prohibited_weapons_nuclear_chemical
- prohibited_extremism_terrorism
- prohibited_organised_crime
- prohibited_fraud
- prohibited_sanctions
</prohibited_categories>

<content>
  <content_id>{content_input['content_id']}</content_id>
  <content_kind>{content_input['content_kind']}</content_kind>
  <surface>{content_input['surface']}</surface>
  <channel_type>{content_input['channel_type']}</channel_type>
  <provider_type>{content_input['provider_type']}</provider_type>
  <message_format>{content_input['message_format']}</message_format>
  <subject>{content_input['message_subject']}</subject>
  <raw_text>{content_input['raw_text_content']}</raw_text>
</content>

<attachments_manifest>
{chr(10).join(file_manifest_lines) if file_manifest_lines else "<none />"}
</attachments_manifest>
""".strip()


def _build_dcx_user_content_policy_check_response_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "moderation_status": {"type": "string"},
            "matched_prohibited_categories": {
                "type": "array",
                "items": {"type": "string"},
            },
            "moderation_reason_summary": {"type": "string"},
            "user_facing_message": {"type": "string"},
            "should_redact_original": {"type": "boolean"},
        },
        "required": [
            "moderation_status",
            "matched_prohibited_categories",
            "moderation_reason_summary",
            "user_facing_message",
            "should_redact_original",
        ],
    }


def _build_fallback_policy_check(
    content_input: dict,
    model_name: str,
    provider_name: str,
    analysis_mode: str,
) -> dict:
    return {
        "provider_name": provider_name,
        "model_name": model_name,
        "prompt_version": PROMPT_VERSION_DCX_USER_CONTENT_POLICY_CHECK,
        "analysis_mode": analysis_mode,
        "policy_check_status": "skipped",
        "moderation_status": "not_reviewed",
        "moderation_reason_summary": "",
        "matched_prohibited_categories": [],
        "user_facing_message": "",
        "should_redact_original": False,
        "usage_metadata": {},
        "raw_output_json": {
            "content_id": content_input.get("content_id"),
            "reason": "GEMINI_API_KEY not configured.",
        },
    }


def _normalize_policy_check_output(
    parsed_output: dict,
    model_name: str,
    provider_name: str,
    analysis_mode: str,
    usage_metadata: dict | None = None,
) -> dict:
    moderation_status = _normalize_moderation_status(parsed_output.get("moderation_status"))
    matched_categories = _normalize_prohibited_category_codes(
        parsed_output.get("matched_prohibited_categories")
    )
    moderation_reason_summary = str(parsed_output.get("moderation_reason_summary") or "").strip()
    user_facing_message = str(parsed_output.get("user_facing_message") or "").strip()
    should_redact_original = parsed_output.get("should_redact_original") is True

    if moderation_status != "prohibited":
        matched_categories = []
        moderation_reason_summary = ""
        user_facing_message = ""
        should_redact_original = False
    else:
        if moderation_reason_summary == "":
            moderation_reason_summary = "The input matched one or more prohibited content categories."
        if user_facing_message == "":
            user_facing_message = "This input was blocked by DCX content policy."
        should_redact_original = True

    return {
        "provider_name": provider_name,
        "model_name": model_name,
        "prompt_version": PROMPT_VERSION_DCX_USER_CONTENT_POLICY_CHECK,
        "analysis_mode": analysis_mode,
        "policy_check_status": "completed",
        "moderation_status": moderation_status,
        "moderation_reason_summary": moderation_reason_summary,
        "matched_prohibited_categories": matched_categories,
        "user_facing_message": user_facing_message,
        "should_redact_original": should_redact_original,
        "usage_metadata": usage_metadata if isinstance(usage_metadata, dict) else {},
        "raw_output_json": parsed_output,
    }


def _normalize_content_input(content_input: dict) -> dict:
    content_id = _coerce_positive_int(content_input.get("content_id"))
    if content_id is None:
        content_id = _coerce_positive_int(content_input.get("message_id")) or 0
    return {
        "content_id": content_id,
        "content_kind": str(content_input.get("content_kind") or "message").strip() or "message",
        "surface": str(content_input.get("surface") or content_input.get("channel_type") or "").strip(),
        "channel_type": str(content_input.get("channel_type") or "").strip(),
        "provider_type": str(content_input.get("provider_type") or "").strip(),
        "message_format": str(content_input.get("message_format") or "text").strip(),
        "message_subject": str(content_input.get("message_subject") or "").strip(),
        "raw_text_content": str(content_input.get("raw_text_content") or "").strip(),
    }


def _normalize_file_input(file_input: dict) -> dict:
    return {
        "attachment_id": _coerce_positive_int(file_input.get("attachment_id")) or 0,
        "file_object_id": _coerce_positive_int(file_input.get("file_object_id")) or 0,
        "file_kind": str(file_input.get("file_kind") or "").strip(),
        "content_type": str(file_input.get("content_type") or "application/octet-stream").split(";")[0].strip(),
        "original_filename": str(file_input.get("original_filename") or "").strip(),
        "file_size_bytes": file_input.get("file_size_bytes"),
        "file_bytes": file_input.get("file_bytes") or b"",
    }


def _normalize_moderation_status(value: Any) -> str:
    normalized_value = str(value or "").strip().lower()
    if normalized_value == "prohibited":
        return "prohibited"
    if normalized_value == "allowed":
        return "allowed"
    return "allowed"


def _normalize_prohibited_category_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized_codes: list[str] = []
    for item in value:
        normalized_item = str(item or "").strip().lower()
        if (
            normalized_item in DCX_USER_CONTENT_POLICY_REASON_CODES
            and normalized_item not in normalized_codes
        ):
            normalized_codes.append(normalized_item)
    return normalized_codes


def _coerce_positive_int(value: Any) -> int | None:
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return None
    return parsed_value if parsed_value > 0 else None


def _escape_prompt_attribute(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
