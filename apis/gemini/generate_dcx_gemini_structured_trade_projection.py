"""
CONTEXT:
This file calls Google Gemini for one structured DCX trade-candidate projection.
It exists so Slice 1 can turn one workflow-routed trade item from an inbound message into a
first raw-plus-normalized trade candidate without adding any new provider plumbing.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)

PROMPT_VERSION_DCX_TRADE_PROJECTION = "dcx_trade_projection_2026_04_28_v1"


def generate_dcx_gemini_structured_trade_projection(
    message_input: dict,
    workflow_item: dict,
    attachment_inputs: list[dict],
    send_gemini_request: Callable[[dict], dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - message_input describes one persisted DCX contact message already analysed once.
        - workflow_item describes one identified trade workflow item from that message.
        - attachment_inputs contains already-analysed attachment summaries relevant to the source message.
        - GEMINI_API_KEY is configured unless send_gemini_request is injected by tests.
      postconditions:
        - Returns one normalized trade candidate payload with raw and normalized fields.
      side_effects:
        - may call Google Gemini over HTTPS
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: trade_projection:{message_id}:{workflow_item_index}:{PROMPT_VERSION_DCX_TRADE_PROJECTION}
      locks: []
      contention_strategy: caller owns projection-item locking

    NARRATIVE:
      WHY this exists:
        - DCX's core value is turning messy real-world trader messages into structured commercial flow.
      WHEN TO USE it:
        - Use it after Prompt 1 has identified one trade workflow item.
      WHEN NOT TO USE it:
        - Do not use it for broad message moderation or for market-topic seeding.
      WHAT CAN GO WRONG:
        - Gemini can fail or return malformed projection fields.
      WHAT COMES NEXT:
        - The resulting trade candidate can be confirmed, corrected, or completed by the trader in later slices.

    TESTS:
      - to be added with first projection smoke coverage

    ERRORS:
      - API_DCX_GEMINI_TRADE_PROJECTION_FAILED:
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
        raise RuntimeError("API_DCX_GEMINI_TRADE_PROJECTION_FAILED")

    request_context = {
        "api_key": api_key,
        "model_name": model_name,
        "prompt_text": _build_dcx_trade_projection_prompt(
            message_input=message_input,
            workflow_item=workflow_item,
            attachment_inputs=attachment_inputs,
        ),
        "response_schema": _build_dcx_trade_projection_response_schema(),
    }

    try:
        response_payload = (send_gemini_request or _send_gemini_generate_content_request)(request_context)
        output_text = str(response_payload.get("output_text", "")).strip()
        parsed_output = json.loads(output_text)
    except Exception as exc:
        raise RuntimeError("API_DCX_GEMINI_TRADE_PROJECTION_FAILED") from exc

    return _normalize_trade_projection_output(
        parsed_output=parsed_output,
        model_name=model_name,
    )


def _send_gemini_generate_content_request(request_context: dict) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=request_context["api_key"])
    response = client.models.generate_content(
        model=request_context["model_name"],
        contents=[request_context["prompt_text"]],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=request_context["response_schema"],
        ),
    )
    return {"output_text": (response.text or "").strip()}


def _build_dcx_trade_projection_prompt(
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
<dcx_task>
Interpret this trade-like workflow item as a senior commodity trade administrator would.
Return JSON only.
</dcx_task>

<trade_projection_rules>
- Preserve what the trader actually communicated.
- Treat this as a trade candidate, not final truth.
- Use raw_* fields to preserve the trader's messy original commercial language.
- Use normalized_* fields only when the message supports a reasonable interpretation.
- If a field is missing or uncertain, leave the normalized value empty/null and mention the gap in missing_required_fields.
- quantity, price, locations, and terms may be partial. Do not invent them.
- A broad commodity trade abstraction is acceptable for MVP:
    amount x thing x place x place x movement x price basis x timing x terms.
- Distinguish clearly between:
    - trade side (buying/selling/wanted/offering)
    - quantity
    - price basis
    - total price
    - origin and destination
- Write one concise trade_summary_text recap that can later be shown back to the trader for confirmation.
</trade_projection_rules>

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


def _build_dcx_trade_projection_response_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "raw_trade_side_text": {"type": "string"},
            "raw_material_text": {"type": "string"},
            "raw_quantity_text": {"type": "string"},
            "raw_price_text": {"type": "string"},
            "raw_origin_text": {"type": "string"},
            "raw_destination_text": {"type": "string"},
            "raw_shipping_method_text": {"type": "string"},
            "raw_incoterm_text": {"type": "string"},
            "raw_delivery_window_text": {"type": "string"},
            "raw_quality_text": {"type": "string"},
            "raw_payment_terms_text": {"type": "string"},
            "raw_counterparty_scope_text": {"type": "string"},
            "normalized_trade_side": {"type": "string"},
            "normalized_material_name": {"type": "string"},
            "normalized_quantity_value": {"type": "number", "nullable": True},
            "normalized_quantity_unit": {"type": "string"},
            "normalized_price_mode": {"type": "string"},
            "normalized_price_value": {"type": "number", "nullable": True},
            "normalized_price_unit_basis": {"type": "string"},
            "normalized_currency_code": {"type": "string"},
            "normalized_total_price_value": {"type": "number", "nullable": True},
            "normalized_origin_location": {"type": "string"},
            "normalized_destination_location": {"type": "string"},
            "normalized_shipping_method": {"type": "string"},
            "normalized_incoterm_code": {"type": "string"},
            "normalized_delivery_window_start_text": {"type": "string"},
            "normalized_delivery_window_end_text": {"type": "string"},
            "normalized_quality_summary_text": {"type": "string"},
            "normalized_payment_terms_summary_text": {"type": "string"},
            "trade_summary_text": {"type": "string"},
            "trade_extraction_notes_text": {"type": "string"},
            "missing_required_fields": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "raw_trade_side_text",
            "raw_material_text",
            "raw_quantity_text",
            "raw_price_text",
            "raw_origin_text",
            "raw_destination_text",
            "raw_shipping_method_text",
            "raw_incoterm_text",
            "raw_delivery_window_text",
            "raw_quality_text",
            "raw_payment_terms_text",
            "raw_counterparty_scope_text",
            "normalized_trade_side",
            "normalized_material_name",
            "normalized_quantity_value",
            "normalized_quantity_unit",
            "normalized_price_mode",
            "normalized_price_value",
            "normalized_price_unit_basis",
            "normalized_currency_code",
            "normalized_total_price_value",
            "normalized_origin_location",
            "normalized_destination_location",
            "normalized_shipping_method",
            "normalized_incoterm_code",
            "normalized_delivery_window_start_text",
            "normalized_delivery_window_end_text",
            "normalized_quality_summary_text",
            "normalized_payment_terms_summary_text",
            "trade_summary_text",
            "trade_extraction_notes_text",
            "missing_required_fields",
        ],
    }


def _normalize_trade_projection_output(parsed_output: dict, model_name: str) -> dict:
    return {
        "model_name": model_name,
        "provider_name": "google_gemini",
        "prompt_version": PROMPT_VERSION_DCX_TRADE_PROJECTION,
        "raw_trade_side_text": _normalize_trade_text_field(parsed_output.get("raw_trade_side_text")),
        "raw_material_text": _normalize_trade_text_field(parsed_output.get("raw_material_text")),
        "raw_quantity_text": _normalize_trade_text_field(parsed_output.get("raw_quantity_text")),
        "raw_price_text": _normalize_trade_text_field(parsed_output.get("raw_price_text")),
        "raw_origin_text": _normalize_trade_text_field(parsed_output.get("raw_origin_text")),
        "raw_destination_text": _normalize_trade_text_field(parsed_output.get("raw_destination_text")),
        "raw_shipping_method_text": _normalize_trade_text_field(parsed_output.get("raw_shipping_method_text")),
        "raw_incoterm_text": _normalize_trade_text_field(parsed_output.get("raw_incoterm_text")),
        "raw_delivery_window_text": _normalize_trade_text_field(parsed_output.get("raw_delivery_window_text")),
        "raw_quality_text": _normalize_trade_text_field(parsed_output.get("raw_quality_text")),
        "raw_payment_terms_text": _normalize_trade_text_field(parsed_output.get("raw_payment_terms_text")),
        "raw_counterparty_scope_text": _normalize_trade_text_field(parsed_output.get("raw_counterparty_scope_text")),
        "normalized_trade_side": _normalize_trade_text_field(parsed_output.get("normalized_trade_side")),
        "normalized_material_name": _normalize_trade_text_field(parsed_output.get("normalized_material_name")),
        "normalized_quantity_value": _coerce_float_or_none(parsed_output.get("normalized_quantity_value")),
        "normalized_quantity_unit": _normalize_trade_text_field(parsed_output.get("normalized_quantity_unit")),
        "normalized_price_mode": _normalize_trade_text_field(parsed_output.get("normalized_price_mode")),
        "normalized_price_value": _coerce_float_or_none(parsed_output.get("normalized_price_value")),
        "normalized_price_unit_basis": _normalize_trade_text_field(parsed_output.get("normalized_price_unit_basis")),
        "normalized_currency_code": _normalize_trade_code_field(parsed_output.get("normalized_currency_code")),
        "normalized_total_price_value": _coerce_float_or_none(parsed_output.get("normalized_total_price_value")),
        "normalized_origin_location": _normalize_trade_text_field(parsed_output.get("normalized_origin_location")),
        "normalized_destination_location": _normalize_trade_text_field(parsed_output.get("normalized_destination_location")),
        "normalized_shipping_method": _normalize_trade_text_field(parsed_output.get("normalized_shipping_method")),
        "normalized_incoterm_code": _normalize_trade_code_field(parsed_output.get("normalized_incoterm_code")),
        "normalized_delivery_window_start_text": _normalize_trade_text_field(parsed_output.get("normalized_delivery_window_start_text")),
        "normalized_delivery_window_end_text": _normalize_trade_text_field(parsed_output.get("normalized_delivery_window_end_text")),
        "normalized_quality_summary_text": _normalize_trade_text_field(parsed_output.get("normalized_quality_summary_text")),
        "normalized_payment_terms_summary_text": _normalize_trade_text_field(parsed_output.get("normalized_payment_terms_summary_text")),
        "trade_summary_text": _normalize_trade_text_field(parsed_output.get("trade_summary_text")),
        "trade_extraction_notes_text": _normalize_trade_text_field(parsed_output.get("trade_extraction_notes_text")),
        "missing_required_fields": _normalize_string_list(parsed_output.get("missing_required_fields")),
        "raw_output_json": parsed_output,
    }


def _coerce_float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized_values: list[str] = []
    for item in value:
        normalized_item = str(item or "").strip()
        if normalized_item != "" and normalized_item not in normalized_values:
            normalized_values.append(normalized_item)
    return normalized_values


def _normalize_trade_text_field(value: Any) -> str:
    normalized_value = str(value or "").strip()
    if normalized_value.lower() in {"not specified", "unknown", "n/a", "none"}:
        return ""
    return normalized_value


def _normalize_trade_code_field(value: Any) -> str:
    normalized_value = _normalize_trade_text_field(value).upper()
    return normalized_value
