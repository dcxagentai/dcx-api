"""
CONTEXT:
This file calls Google Gemini for one structured DCX contact-message analysis.
It exists so the Messages pipeline can send one message envelope plus supported attachment bytes
to one multimodal model and receive one validated JSON-shaped analysis result.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)

PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS = "dcx_contact_message_analysis_2026_04_28_v4"
DCX_MESSAGE_TEXT_SUMMARY_WORD_COUNT_THRESHOLD = 100
DCX_MESSAGE_TEXT_SYNTHESIS_WORD_COUNT_THRESHOLD = 500
DCX_WORKFLOW_ITEM_KINDS = ("trade", "market_topic", "other")
DCX_WORKFLOW_ITEM_CONFIDENCE_LABELS = ("high", "medium", "low")
DCX_PROHIBITED_MESSAGE_REASON_CODES = (
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


def generate_dcx_gemini_structured_message_analysis(
    message_input: dict,
    file_inputs: list[dict],
    send_gemini_request: Callable[[dict], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - message_input describes one persisted DCX contact message.
        - file_inputs contains zero or more supported file parts with file_object_id, attachment_id,
          content_type, original_filename, and file_bytes.
        - GEMINI_API_KEY is configured unless send_gemini_request is injected by tests.
      postconditions:
        - Returns one normalized analysis payload with message-level summary, workflow routing,
          and per-file analysis.
        - Uses a strict prompt and JSON response shape suitable for database writes.
      side_effects:
        - may call Google Gemini over HTTPS
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: message_analysis:{message_id}:prompt:{PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS}
      locks: []
      contention_strategy: no local locks; the caller owns message/job locking

    NARRATIVE:
      WHY this exists:
        - DCX receives mixed trader messages: subject, text, images, audio, and documents. The first
          real AI layer should understand each element and the whole message together.
      WHEN TO USE it:
        - Use it after the raw message and all attachments have been stored and before the message is
          marked ready for the trader.
      WHEN NOT TO USE it:
        - Do not use it as the final structured trade extractor.
      WHAT CAN GO WRONG:
        - Gemini credentials may be missing.
        - The SDK may not support the file type or structured-output config in the current environment.
        - The model can return malformed JSON despite instructions.
      WHAT COMES NEXT:
        - Later processing can split large files into per-file jobs and reuse the same output contract.

    TESTS:
      - returns_fallback_message_analysis_when_gemini_api_key_is_missing
      - returns_structured_message_analysis_from_injected_gemini_payload

    ERRORS:
      - API_DCX_GEMINI_MESSAGE_ANALYSIS_FAILED:
          suggested_action: Retry after confirming Gemini credentials, SDK version, and provider health.
          common_causes:
            - missing GEMINI_API_KEY
            - unsupported model name
            - malformed model output
            - transient provider failure
          recovery_steps:
            - Verify GEMINI_API_KEY and GEMINI_MESSAGE_ANALYSIS_MODEL.
            - Retry after provider health is restored.
          retry_safe: true

    CODE:
    """
    normalized_message_input = _normalize_message_input(message_input)
    normalized_file_inputs = [_normalize_file_input(file_input) for file_input in file_inputs]

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = read_dcx_gemini_message_analysis_model_name()

    if api_key == "" and send_gemini_request is None:
        return _build_fallback_message_analysis(
            message_input=normalized_message_input,
            file_inputs=normalized_file_inputs,
            model_name="",
            provider_name="google_gemini",
            analysis_mode="fallback_no_model",
        )

    request_context = {
        "api_key": api_key,
        "model_name": model_name,
        "prompt_text": _build_dcx_message_analysis_prompt(
            message_input=normalized_message_input,
            file_inputs=normalized_file_inputs,
        ),
        "file_inputs": normalized_file_inputs,
        "response_schema": _build_dcx_message_analysis_response_schema(),
    }

    try:
        response_payload = (send_gemini_request or _send_gemini_generate_content_request)(request_context)
        output_text = str(response_payload.get("output_text", "")).strip()
        parsed_output = json.loads(output_text)
    except Exception as exc:
        raise RuntimeError("API_DCX_GEMINI_MESSAGE_ANALYSIS_FAILED") from exc

    return _normalize_gemini_message_analysis_output(
        parsed_output=parsed_output,
        message_input=normalized_message_input,
        file_inputs=normalized_file_inputs,
        model_name=model_name,
        provider_name="google_gemini",
        analysis_mode="gemini_generate_content",
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

    response = client.models.generate_content(
        model=request_context["model_name"],
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=request_context["response_schema"],
        ),
    )
    return {"output_text": (response.text or "").strip()}


def _build_dcx_message_analysis_prompt(message_input: dict, file_inputs: list[dict]) -> str:
    raw_text_word_count = _count_words(message_input["raw_text_content"])
    text_summary_requested = raw_text_word_count >= DCX_MESSAGE_TEXT_SUMMARY_WORD_COUNT_THRESHOLD
    text_synthesis_requested = raw_text_word_count >= DCX_MESSAGE_TEXT_SYNTHESIS_WORD_COUNT_THRESHOLD
    message_summary_instruction = (
        "- Write a 1-3 sentence summary of the main text."
        if text_summary_requested
        else ""
    )
    text_synthesis_instruction = (
        """
        - Produce a detailed synthesis of the main text, as a senior editor or intelligence anaalyst would, with all relevant details, markers, facts, nuances, references and discourse. 
        Group your synthesis into 10 top detailed points. Length should be 25 percent or less of original text. Return as 10 point markdown unordered list.
        """
        if text_synthesis_requested
        else ""
    )
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
Describe and analyse this message and its parts.
Return JSON only. Do not wrap JSON in markdown.
</dcx_task>

<analysis_rules>
- Preserve precise meaning. Do not invent deal terms.
- Consider each element of the message, individually and as part of the whole.
- Identify the language the message is written in. Return the ISO language code.
{message_summary_instruction}
{text_synthesis_instruction}
- After evaluating moderation, identify one or more workflow items from the message.
- Workflow routing must consider the whole message context, not only the main text body.
- If the raw text is empty, very short, ambiguous, or purely incidental, use the attachment content and
  the attachment-level description/transcription/summary/synthesis/context to decide workflow routing.
- A workflow item is one distinct commercially meaningful or user-meaningful unit that should be routed
  into a later product flow.
- A single message may contain:
    - multiple trade items;
    - multiple market-topic items;
    - a mix of trade items, market-topic items, and other items.
- If the message is prohibited, moderation overrides workflow routing. In that case:
    - set moderation_status = "prohibited";
    - set primary_workflow_kind = "";
    - return workflow_items = [].

- All attachments require:
    - a 1-3 sentence summary;
    - a contextual note describing how the attachment contributes to the message;

- If an attachment is audio:
    - provide a precise, literal transcription of the audio file;
    - If there are multiple speakers, attribute each phrase correctly and separate phrases from each speaker with double line breaks:
        Speaker A: xxx
        `\\n\\n`
        Speaker B: xxx
        `\\n\\n`
        Speaker A: xxx
        `\\n\\n`
        Speaker B: xxx
        `\\n\\n`
    - After transcribing the audio precisely, generate a detailed synthesis and a 1-3 sentence summary;
    - Return an empty string for description;

- If an attachment is an image:
    - describe the visible content as precisely as a senior art director, news editor or visual forensic analyst would;
    - extract all visible text and include it in the image description;
    - Return empty strings for transcription and synthesis;

- If an attachment is a document:
    - Generate a detailed synthesis and a 1-3 sentence summary;
    - Return empty strings for description and transcription;

- Describe each attachment's role within or contribution to the overall context of the message;
- Use empty strings for fields that do not apply.
- Return one moderation decision for the whole message:
    - moderation_status = "allowed" when no prohibited content is found;
    - moderation_status = "prohibited" when any part of the message or any attachment matches one or more prohibited categories.
- If moderation_status = "prohibited":
    - include every matching prohibited category code in matched_prohibited_categories;
    - include a short moderation_reason_summary explaining what triggered the block;
    - do not soften or omit categories just because the message is commercial or framed as a trade.
</analysis_rules>

<workflow_taxonomy>
- trade:
    Use this when the message contains any item, offer, bid, ask, negotiation element, logistics step,
    or commercially actionable reference that pertains to an actual trade or part of a trade process,
    whether new or existing.
    Examples:
      - "Selling 500 MT soybean meal FOB Santos."
      - "Need freight quote for moving copper cathodes from Tema to Antwerp."
      - "Buyer confirms interest in 2 containers if payment terms hold."

- market_topic:
    Use this when the message contains trader-relevant market, business, commodity, policy, sanctions,
    logistics, or commercial discussion that is not itself an actionable structured trade item.
    Examples:
      - "How do new cocoa export taxes affect availability next quarter?"
      - "What are traders saying about sanctions on Russian diesel?"
      - "Attached article about port congestion in Lagos."

- other:
    Use this when the message contains content that is not a trade item and not a trader-relevant market topic.
    Examples:
      - personal or accidental messages
      - general chatter unrelated to trading
      - irrelevant media with no business context

- prohibited override:
    Discussion about sanctions, controlled goods, or prohibited material as market context can still be allowed
    as a market_topic.
    Attempts to buy, sell, move, source, route, or evade controls around prohibited materials or sanctions
    are prohibited.
</workflow_taxonomy>

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

<message>
  <message_id>{message_input['message_id']}</message_id>
  <channel_type>{message_input['channel_type']}</channel_type>
  <provider_type>{message_input['provider_type']}</provider_type>
  <message_format>{message_input['message_format']}</message_format>
  <subject>{message_input['message_subject']}</subject>
  <raw_text>{message_input['raw_text_content']}</raw_text>
</message>

<attachments_manifest>
{chr(10).join(file_manifest_lines) if file_manifest_lines else "<none />"}
</attachments_manifest>
""".strip()


def _build_dcx_message_analysis_response_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "message_language_code": {"type": "STRING", "nullable": True},
            "message_summary": {"type": "string"},
            "message_text_synthesis": {"type": "string"},
            "moderation_status": {"type": "string"},
            "moderation_reason_summary": {"type": "string"},
            "primary_workflow_kind": {"type": "string"},
            "workflow_reason_summary": {"type": "string"},
            "workflow_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_kind": {"type": "string"},
                        "item_title": {"type": "string"},
                        "item_summary": {"type": "string"},
                        "source_excerpt_text": {"type": "string"},
                        "referenced_attachment_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "confidence_label": {"type": "string"},
                    },
                    "required": [
                        "item_kind",
                        "item_title",
                        "item_summary",
                        "source_excerpt_text",
                        "referenced_attachment_ids",
                        "confidence_label",
                    ],
                },
            },
            "matched_prohibited_categories": {
                "type": "array",
                "items": {"type": "string"},
            },
            "attachments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "attachment_id": {"type": "integer"},
                        "file_object_id": {"type": "integer"},
                        "filename": {"type": "string"},
                        "file_kind": {"type": "string"},
                        "language_code": {"type": "STRING", "nullable": True},
                        "summary": {"type": "string"},
                        "description": {"type": "string"},
                        "transcription": {"type": "string"},
                        "synthesis": {"type": "string"},
                        "context_within_message": {"type": "string"},
                    },
                    "required": [
                        "attachment_id",
                        "file_object_id",
                        "filename",
                        "file_kind",
                        "language_code",
                        "summary",
                        "description",
                        "transcription",
                        "synthesis",
                        "context_within_message",
                    ],
                },
            },
        },
        "required": [
            "message_language_code",
            "message_summary",
            "message_text_synthesis",
            "moderation_status",
            "moderation_reason_summary",
            "primary_workflow_kind",
            "workflow_reason_summary",
            "workflow_items",
            "matched_prohibited_categories",
            "attachments",
        ],
    }


def _normalize_gemini_message_analysis_output(
    parsed_output: dict,
    message_input: dict,
    file_inputs: list[dict],
    model_name: str,
    provider_name: str,
    analysis_mode: str,
) -> dict:
    raw_text_word_count = _count_words(message_input.get("raw_text_content", ""))
    known_file_ids = {file_input["file_object_id"] for file_input in file_inputs}
    known_file_kinds_by_id = {
        file_input["file_object_id"]: file_input["file_kind"]
        for file_input in file_inputs
    }
    normalized_attachments = []
    for attachment_output in parsed_output.get("attachments", []):
        if not isinstance(attachment_output, dict):
            continue
        file_object_id = _coerce_positive_int(attachment_output.get("file_object_id"))
        attachment_id = _coerce_positive_int(attachment_output.get("attachment_id"))
        if file_object_id is None or attachment_id is None or file_object_id not in known_file_ids:
            continue
        canonical_file_kind = known_file_kinds_by_id.get(file_object_id) or str(attachment_output.get("file_kind") or "").strip()
        attachment_summary = str(attachment_output.get("summary") or "").strip()
        attachment_description = str(attachment_output.get("description") or "").strip()
        attachment_transcription = str(attachment_output.get("transcription") or "").strip()
        attachment_synthesis = str(attachment_output.get("synthesis") or "").strip()

        if canonical_file_kind == "image":
            attachment_transcription = ""
            attachment_synthesis = ""
        elif canonical_file_kind == "audio":
            attachment_description = ""
            attachment_transcription = _normalize_audio_transcription_paragraphs(attachment_transcription)
        elif canonical_file_kind == "document":
            attachment_description = ""
            attachment_transcription = ""
        else:
            attachment_description = ""
            attachment_transcription = ""
            attachment_synthesis = ""
        normalized_attachments.append(
            {
                "attachment_id": attachment_id,
                "file_object_id": file_object_id,
                "filename": str(attachment_output.get("filename") or "").strip() or _read_original_filename_for_file_object_id(file_inputs, file_object_id),
                "file_kind": canonical_file_kind,
                "language_code": _normalize_language_code(attachment_output.get("language_code")),
                "summary": attachment_summary,
                "description": attachment_description,
                "transcription": attachment_transcription,
                "synthesis": attachment_synthesis,
                "context_within_message": str(attachment_output.get("context_within_message") or "").strip(),
                "analysis_status": "completed",
            }
        )

    message_summary = str(parsed_output.get("message_summary") or "").strip()
    if raw_text_word_count < DCX_MESSAGE_TEXT_SUMMARY_WORD_COUNT_THRESHOLD:
        message_summary = ""
    elif message_summary == "":
        message_summary = _fallback_message_summary(message_input)

    message_text_synthesis = str(parsed_output.get("message_text_synthesis") or "").strip()
    if raw_text_word_count < DCX_MESSAGE_TEXT_SYNTHESIS_WORD_COUNT_THRESHOLD:
        message_text_synthesis = ""

    moderation_status = _normalize_moderation_status(parsed_output.get("moderation_status"))
    moderation_reason_codes = _normalize_prohibited_category_codes(
        parsed_output.get("matched_prohibited_categories")
    )
    moderation_reason_summary = str(parsed_output.get("moderation_reason_summary") or "").strip()
    if moderation_status != "prohibited":
        moderation_reason_codes = []
        moderation_reason_summary = ""
    elif moderation_reason_summary == "":
        moderation_reason_summary = "The message matched one or more prohibited content categories."

    normalized_workflow_items = _normalize_workflow_items(
        parsed_output.get("workflow_items"),
        file_inputs=file_inputs,
    )
    if moderation_status != "prohibited" and not normalized_workflow_items:
        normalized_workflow_items = _build_fallback_workflow_items_from_message_context(
            message_input=message_input,
            normalized_attachments=normalized_attachments,
        )
    primary_workflow_kind = _normalize_primary_workflow_kind(
        parsed_output.get("primary_workflow_kind"),
        normalized_workflow_items=normalized_workflow_items,
        moderation_status=moderation_status,
    )
    workflow_reason_summary = str(parsed_output.get("workflow_reason_summary") or "").strip()
    if moderation_status == "prohibited":
        primary_workflow_kind = ""
        workflow_reason_summary = ""
        normalized_workflow_items = []
    elif workflow_reason_summary == "" and normalized_workflow_items:
        workflow_reason_summary = f"Identified {len(normalized_workflow_items)} workflow item(s) from the message."

    return {
        "provider_name": provider_name,
        "model_name": model_name,
        "prompt_version": PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS,
        "analysis_mode": analysis_mode,
        "message_language_code": _normalize_language_code(parsed_output.get("message_language_code")),
        "message_summary": message_summary,
        "message_text_synthesis": message_text_synthesis,
        "message_analysis_status": "completed",
        "moderation_status": moderation_status,
        "moderation_reason_summary": moderation_reason_summary,
        "matched_prohibited_categories": moderation_reason_codes,
        "primary_workflow_kind": primary_workflow_kind,
        "workflow_reason_summary": workflow_reason_summary,
        "workflow_classification_status": "completed",
        "workflow_items": normalized_workflow_items,
        "attachments": normalized_attachments,
        "raw_output_json": parsed_output,
    }


def _build_fallback_message_analysis(
    message_input: dict,
    file_inputs: list[dict],
    model_name: str,
    provider_name: str,
    analysis_mode: str,
) -> dict:
    message_raw_text = (message_input.get("raw_text_content") or "").strip()
    should_summarize_message_text = _count_words(message_raw_text) >= DCX_MESSAGE_TEXT_SUMMARY_WORD_COUNT_THRESHOLD
    return {
        "provider_name": provider_name,
        "model_name": model_name,
        "prompt_version": PROMPT_VERSION_DCX_CONTACT_MESSAGE_ANALYSIS,
        "analysis_mode": analysis_mode,
        "message_language_code": None,
        "message_summary": _fallback_message_summary(message_input) if should_summarize_message_text else "",
        "message_text_synthesis": "",
        "message_analysis_status": "completed",
        "moderation_status": "not_reviewed",
        "moderation_reason_summary": "",
        "matched_prohibited_categories": [],
        "primary_workflow_kind": "",
        "workflow_reason_summary": "",
        "workflow_classification_status": "not_started",
        "workflow_items": [],
        "attachments": [
            {
                "attachment_id": file_input["attachment_id"],
                "file_object_id": file_input["file_object_id"],
                "filename": file_input["original_filename"],
                "file_kind": file_input["file_kind"],
                "language_code": None,
                "summary": "File stored. No model analysis is configured in this environment.",
                "description": "",
                "transcription": "",
                "synthesis": "",
                "context_within_message": "Attached to this message.",
                "analysis_status": "skipped",
            }
            for file_input in file_inputs
        ],
        "raw_output_json": {},
    }


def _fallback_message_summary(message_input: dict) -> str:
    subject = (message_input.get("message_subject") or "").strip()
    raw_text = (message_input.get("raw_text_content") or "").strip()
    if subject != "":
        return subject
    if raw_text != "":
        return raw_text[:500]
    return "No textual content was available for message analysis."


def _read_original_filename_for_file_object_id(file_inputs: list[dict], file_object_id: int) -> str:
    for file_input in file_inputs:
        if file_input.get("file_object_id") == file_object_id:
            return str(file_input.get("original_filename") or "").strip()
    return ""


def _normalize_message_input(message_input: dict) -> dict:
    return {
        "message_id": _coerce_positive_int(message_input.get("message_id")) or 0,
        "channel_type": str(message_input.get("channel_type") or "").strip(),
        "provider_type": str(message_input.get("provider_type") or "").strip(),
        "message_format": str(message_input.get("message_format") or "").strip(),
        "message_subject": str(message_input.get("message_subject") or "").strip(),
        "raw_text_content": str(message_input.get("raw_text_content") or "").strip(),
    }


def _count_words(value: str) -> int:
    return len([word for word in value.replace("\n", " ").split(" ") if word.strip() != ""])


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


def _normalize_language_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized_value = value.strip().lower()
    if normalized_value == "":
        return None
    return normalized_value[:12]


def _normalize_moderation_status(value: Any) -> str:
    normalized_value = str(value or "").strip().lower()
    if normalized_value == "prohibited":
        return "prohibited"
    if normalized_value == "allowed":
        return "allowed"
    return "allowed"


def _normalize_workflow_items(value: Any, file_inputs: list[dict]) -> list[dict]:
    if not isinstance(value, list):
        return []

    known_attachment_ids = {
        int(file_input["attachment_id"])
        for file_input in file_inputs
        if isinstance(file_input.get("attachment_id"), int)
    }
    normalized_items: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        item_kind = str(item.get("item_kind") or "").strip().lower()
        if item_kind not in DCX_WORKFLOW_ITEM_KINDS:
            continue
        referenced_attachment_ids = []
        for referenced_attachment_id in item.get("referenced_attachment_ids") or []:
            attachment_id = _coerce_positive_int(referenced_attachment_id)
            if attachment_id is not None and attachment_id in known_attachment_ids and attachment_id not in referenced_attachment_ids:
                referenced_attachment_ids.append(attachment_id)
        confidence_label = str(item.get("confidence_label") or "").strip().lower()
        if confidence_label not in DCX_WORKFLOW_ITEM_CONFIDENCE_LABELS:
            confidence_label = "medium"
        normalized_items.append(
            {
                "item_kind": item_kind,
                "item_title": str(item.get("item_title") or "").strip(),
                "item_summary": str(item.get("item_summary") or "").strip(),
                "source_excerpt_text": str(item.get("source_excerpt_text") or "").strip(),
                "referenced_attachment_ids": referenced_attachment_ids,
                "confidence_label": confidence_label,
            }
        )
    return normalized_items


def _build_fallback_workflow_items_from_message_context(
    message_input: dict,
    normalized_attachments: list[dict],
) -> list[dict]:
    raw_text = str(message_input.get("raw_text_content") or "").strip()
    raw_text_word_count = _count_words(raw_text)
    if raw_text_word_count > 3 or not normalized_attachments:
        return []

    fallback_summary_parts: list[str] = []
    referenced_attachment_ids: list[int] = []
    for attachment in normalized_attachments:
        attachment_context_text = (
            str(attachment.get("summary") or "").strip()
            or str(attachment.get("description") or "").strip()
            or str(attachment.get("transcription") or "").strip()
            or str(attachment.get("synthesis") or "").strip()
            or str(attachment.get("context_within_message") or "").strip()
        )
        if attachment_context_text != "":
            fallback_summary_parts.append(attachment_context_text)
        attachment_id = _coerce_positive_int(attachment.get("attachment_id"))
        if attachment_id is not None and attachment_id not in referenced_attachment_ids:
            referenced_attachment_ids.append(attachment_id)

    fallback_summary_text = " ".join(fallback_summary_parts).strip()
    if fallback_summary_text == "":
        fallback_summary_text = "Attachment-led message with no meaningful body text."

    return [
        {
            "item_kind": "other",
            "item_title": "Attachment-led message",
            "item_summary": fallback_summary_text[:4000],
            "source_excerpt_text": fallback_summary_text[:4000],
            "referenced_attachment_ids": referenced_attachment_ids,
            "confidence_label": "medium",
        }
    ]


def _normalize_primary_workflow_kind(
    value: Any,
    normalized_workflow_items: list[dict],
    moderation_status: str,
) -> str:
    if moderation_status == "prohibited":
        return ""
    normalized_value = str(value or "").strip().lower()
    if normalized_value in DCX_WORKFLOW_ITEM_KINDS:
        return normalized_value
    if any(item["item_kind"] == "trade" for item in normalized_workflow_items):
        return "trade"
    if any(item["item_kind"] == "market_topic" for item in normalized_workflow_items):
        return "market_topic"
    if any(item["item_kind"] == "other" for item in normalized_workflow_items):
        return "other"
    return ""


def _normalize_prohibited_category_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized_codes: list[str] = []
    for item in value:
        normalized_item = str(item or "").strip().lower()
        if (
            normalized_item in DCX_PROHIBITED_MESSAGE_REASON_CODES
            and normalized_item not in normalized_codes
        ):
            normalized_codes.append(normalized_item)
    return normalized_codes


def _normalize_audio_transcription_paragraphs(value: str) -> str:
    normalized_value = value.strip()
    if normalized_value == "":
        return ""
    speaker_chunks = [
        chunk.strip()
        for chunk in re.split(r"(?=Speaker\s+\w+\s*:)", normalized_value)
        if chunk.strip() != ""
    ]
    if len(speaker_chunks) <= 1:
        return normalized_value
    normalized_chunks = [
        re.sub(r"(\bSpeaker\s+\w+\s*:)\s*", r"\1 ", chunk).strip()
        for chunk in speaker_chunks
    ]
    return "\n\n".join(normalized_chunks).strip()


def _coerce_positive_int(value: Any) -> int | None:
    try:
        integer_value = int(value)
    except (TypeError, ValueError):
        return None
    if integer_value <= 0:
        return None
    return integer_value


def _escape_prompt_attribute(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
