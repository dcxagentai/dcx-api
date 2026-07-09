"""
CONTEXT:
This file asks Gemini to translate one structured admin content payload into one target language.
It exists for CMS/email AI translation jobs where the backend needs field-level JSON back, not a
freeform translated paragraph.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from collections import Counter
from typing import Any, Callable

from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)
from apis.gemini.read_dcx_gemini_usage_metadata import read_dcx_gemini_usage_metadata

PROMPT_VERSION_DCX_ADMIN_STRUCTURED_TRANSLATION = "dcx_admin_structured_translation_2026_07_09_v4"
MAX_STRUCTURED_TRANSLATION_RESPONSE_ATTEMPTS = 3

_PLACEHOLDER_PATTERN = re.compile(r"{{\s*[^{}]+\s*}}")
_URL_PATTERN = re.compile(r"https?://[^\s)>\]]+")
_NUMBER_PATTERN = re.compile(r"\d+(?:[.,\u066B\u066C\u00A0\u202F' ]\d+)*")
_COMMERCIAL_TOKEN_PATTERN = re.compile(
    r"\b(?:USD|EUR|GBP|CNY|RMB|AED|FOB|CIF|CFR|DAP|DDP|EXW|LC|L/C|MT|KG|G|LB|OZ|SGS|HS|ISO)\b",
    re.IGNORECASE,
)

LANGUAGE_PROFILE_BY_CODE = {
    "ar": "Arabic, Modern Standard Arabic, right-to-left business register",
    "de": "German for Germany",
    "en": "English",
    "es": "Spanish from Spain",
    "fr": "French from France",
    "hi": "Hindi in Devanagari script",
    "id": "Indonesian",
    "pt": "Portuguese from Portugal",
    "ru": "Russian",
    "tr": "Turkish",
    "ur": "Urdu, right-to-left business register",
    "vi": "Vietnamese",
    "zh": "Simplified Chinese business register",
}


def translate_dcx_gemini_structured_admin_content(
    entity_kind: str,
    source_language_code: str,
    target_language_code: str,
    source_fields: dict[str, str],
    send_gemini_request: Callable[[dict], dict] | None = None,
) -> dict:
    normalized_source_fields = {
        str(key): str(value or "")
        for key, value in (source_fields or {}).items()
    }
    normalized_source_language_code = source_language_code.strip().lower()
    normalized_target_language_code = target_language_code.strip().lower()
    if (
        entity_kind.strip() == ""
        or normalized_source_language_code == ""
        or normalized_target_language_code == ""
        or not normalized_source_fields
    ):
        raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_INVALID")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = read_dcx_gemini_message_analysis_model_name()
    if api_key == "" and send_gemini_request is None:
        raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_FAILED")

    prompt_text = ""
    usage_metadata = {}
    validation_feedback = None
    translated_fields = {}
    for attempt_number in range(1, MAX_STRUCTURED_TRANSLATION_RESPONSE_ATTEMPTS + 1):
        prompt_text = _build_admin_translation_prompt(
            entity_kind=entity_kind.strip(),
            source_language_code=normalized_source_language_code,
            target_language_code=normalized_target_language_code,
            source_fields=normalized_source_fields,
            validation_feedback=validation_feedback,
        )
        try:
            response_payload = (send_gemini_request or _send_gemini_generate_content_request)(
                {
                    "api_key": api_key,
                    "model_name": model_name,
                    "prompt_text": prompt_text,
                }
            )
            output_text = str(response_payload.get("output_text", "")).strip()
            usage_metadata = response_payload.get("usage_metadata") if isinstance(response_payload, dict) else {}
            translated_fields = _read_translated_fields_from_output_text(
                output_text=output_text,
                expected_language_code=normalized_target_language_code,
                expected_field_names=sorted(normalized_source_fields.keys()),
            )
            _validate_translated_fields(
                source_fields=normalized_source_fields,
                translated_fields=translated_fields,
            )
            break
        except RuntimeError as exc:
            if (
                not _is_retryable_translation_response_error(exc)
                or attempt_number >= MAX_STRUCTURED_TRANSLATION_RESPONSE_ATTEMPTS
            ):
                raise
            validation_feedback = _build_validation_feedback(
                error_detail=str(exc),
                previous_output_text=output_text if "output_text" in locals() else "",
            )
        except Exception as exc:
            raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_FAILED") from exc
    else:
        raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_FAILED")

    resolved_usage_metadata = usage_metadata if isinstance(usage_metadata, dict) else {}
    resolved_usage_metadata = {
        **resolved_usage_metadata,
        "translation_response_attempt_count": attempt_number,
    }

    return {
        "translated_fields": translated_fields,
        "provider_name": "google_gemini",
        "model_name": model_name,
        "prompt_version": PROMPT_VERSION_DCX_ADMIN_STRUCTURED_TRANSLATION,
        "usage_metadata": resolved_usage_metadata,
        "prompt_fingerprint": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
    }


def _send_gemini_generate_content_request(request_context: dict) -> dict:
    from google import genai

    client = genai.Client(api_key=request_context["api_key"])
    response = client.models.generate_content(
        model=request_context["model_name"],
        contents=[request_context["prompt_text"]],
    )
    return {
        "output_text": (response.text or "").strip(),
        "usage_metadata": read_dcx_gemini_usage_metadata(response),
    }


def _build_admin_translation_prompt(
    entity_kind: str,
    source_language_code: str,
    target_language_code: str,
    source_fields: dict[str, str],
    validation_feedback: dict | None = None,
) -> str:
    target_language_profile = LANGUAGE_PROFILE_BY_CODE.get(
        target_language_code,
        f"language code {target_language_code}",
    )
    preservation_manifest = _build_preservation_manifest(source_fields)
    validation_feedback_block = _build_validation_feedback_block(validation_feedback)
    return f"""
<dcx_task>
Translate structured DCX admin content from source_language_code={source_language_code} to target_language_code={target_language_code}.
Target locale/register: {target_language_profile}.
Return only valid JSON. Do not wrap in markdown. Do not add commentary.
</dcx_task>

<json_contract>
Return exactly this shape:
{{
  "target_language_code": "{target_language_code}",
  "fields": {{
    "field_name": "translated value"
  }}
}}
The fields object must contain exactly the same field names as the input.
</json_contract>

<translation_rules>
- Translate naturally and professionally for commodities, markets, currency, and international business.
- Preserve the commercial meaning exactly.
- Preserve quantities, grades, units, currencies, dates, locations, ports, company names, URLs, placeholders, and markdown link targets.
- Preserve every digit-bearing number as digits. Do not spell source digit tokens out as words, remove them, or introduce new digit tokens.
- Locale punctuation such as decimal commas, non-breaking-space group separators, and native digit glyphs is allowed only when it preserves the same number.
- The preservation manifest is binding. For each field, make sure every listed source_token is represented by a digit-bearing equivalent in that translated field.
- Translate field text, headings, and link labels where appropriate.
- For fields named `page_slug` or `category_slug`, return a concise translated URL path segment
  in the target language and script. Use hyphens between words where the language uses word
  spacing. Do not include slashes, spaces, query strings, fragments, quotes, emoji, leading
  hyphens, or trailing hyphens.
- Keep abbreviations such as FOB, CIF, CFR, LC, MT, SGS, HS, ISO, USD, EUR, GBP, CNY, AED unchanged unless local business usage strongly requires otherwise.
- Preserve markdown structure and line breaks.
- If a field is empty, return an empty string for that field.
- If the text is already in the target language, return it unchanged.
</translation_rules>

<entity_kind>
{entity_kind}
</entity_kind>

<source_fields_json>
{json.dumps(source_fields, ensure_ascii=False, sort_keys=True)}
</source_fields_json>

<preservation_manifest_json>
{json.dumps(preservation_manifest, ensure_ascii=False, sort_keys=True)}
</preservation_manifest_json>

{validation_feedback_block}
""".strip()


def _build_preservation_manifest(source_fields: dict[str, str]) -> dict:
    return {
        "number_tokens_by_field": {
            field_name: [
                {
                    "source_token": token,
                    "normalized_digits": _normalize_number_token(token),
                }
                for token in _NUMBER_PATTERN.findall(source_value or "")
                if _normalize_number_token(token) != ""
            ]
            for field_name, source_value in source_fields.items()
        },
        "placeholder_tokens_by_field": {
            field_name: _PLACEHOLDER_PATTERN.findall(source_value or "")
            for field_name, source_value in source_fields.items()
        },
        "url_tokens_by_field": {
            field_name: _URL_PATTERN.findall(source_value or "")
            for field_name, source_value in source_fields.items()
        },
        "commercial_tokens_by_field": {
            field_name: _COMMERCIAL_TOKEN_PATTERN.findall(source_value or "")
            for field_name, source_value in source_fields.items()
        },
    }


def _build_validation_feedback(error_detail: str, previous_output_text: str) -> dict:
    return {
        "previous_error": error_detail,
        "previous_output_text": previous_output_text[:8000],
        "required_action": (
            "Return the full JSON contract again. Correct the failed field while preserving "
            "the same source meaning. If a number mismatch is reported, every source number "
            "token listed in the preservation manifest must appear as a digit-bearing equivalent "
            "in the same translated field, and no new digit-bearing number may be introduced."
        ),
    }


def _build_validation_feedback_block(validation_feedback: dict | None) -> str:
    if not isinstance(validation_feedback, dict):
        return ""
    return f"""
<previous_validation_failure>
The previous response failed automated validation. Fix it and return the full JSON contract again.
{json.dumps(validation_feedback, ensure_ascii=False, sort_keys=True)}
</previous_validation_failure>
""".strip()


def _is_retryable_translation_response_error(exc: RuntimeError) -> bool:
    error_code = str(exc).split(":", 1)[0]
    return error_code in {
        "API_DCX_GEMINI_ADMIN_TRANSLATION_INVALID_JSON",
        "API_DCX_GEMINI_ADMIN_TRANSLATION_LANGUAGE_MISMATCH",
        "API_DCX_GEMINI_ADMIN_TRANSLATION_FIELD_MISMATCH",
        "API_DCX_GEMINI_ADMIN_TRANSLATION_EMPTY_FIELD",
        "API_DCX_GEMINI_ADMIN_TRANSLATION_PLACEHOLDER_MISMATCH",
        "API_DCX_GEMINI_ADMIN_TRANSLATION_URL_MISMATCH",
        "API_DCX_GEMINI_ADMIN_TRANSLATION_COMMERCIAL_TOKEN_MISMATCH",
        "API_DCX_GEMINI_ADMIN_TRANSLATION_NUMBER_MISMATCH",
    }


def _read_translated_fields_from_output_text(
    output_text: str,
    expected_language_code: str,
    expected_field_names: list[str],
) -> dict[str, str]:
    cleaned_output_text = output_text.strip()
    if cleaned_output_text.startswith("```"):
        cleaned_output_text = re.sub(r"^```(?:json)?\s*", "", cleaned_output_text)
        cleaned_output_text = re.sub(r"\s*```$", "", cleaned_output_text)

    try:
        payload = json.loads(cleaned_output_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_INVALID_JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_INVALID_JSON")
    if str(payload.get("target_language_code", "")).strip().lower() != expected_language_code:
        raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_LANGUAGE_MISMATCH")

    fields = payload.get("fields")
    if not isinstance(fields, dict):
        raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_INVALID_JSON")

    if sorted(str(key) for key in fields.keys()) != expected_field_names:
        raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_FIELD_MISMATCH")

    return {
        field_name: str(fields.get(field_name, ""))
        for field_name in expected_field_names
    }


def _validate_translated_fields(
    source_fields: dict[str, str],
    translated_fields: dict[str, str],
) -> None:
    for field_name, source_value in source_fields.items():
        translated_value = translated_fields.get(field_name, "")
        if source_value.strip() != "" and translated_value.strip() == "":
            raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_EMPTY_FIELD")

        _validate_same_tokens(
            source_value=source_value,
            translated_value=translated_value,
            pattern=_PLACEHOLDER_PATTERN,
            error_code="API_DCX_GEMINI_ADMIN_TRANSLATION_PLACEHOLDER_MISMATCH",
        )
        _validate_same_tokens(
            source_value=source_value,
            translated_value=translated_value,
            pattern=_URL_PATTERN,
            error_code="API_DCX_GEMINI_ADMIN_TRANSLATION_URL_MISMATCH",
        )
        _validate_same_tokens(
            source_value=source_value,
            translated_value=translated_value,
            pattern=_COMMERCIAL_TOKEN_PATTERN,
            error_code="API_DCX_GEMINI_ADMIN_TRANSLATION_COMMERCIAL_TOKEN_MISMATCH",
            casefold=True,
        )
        _validate_same_number_shapes(
            field_name=field_name,
            source_value=source_value,
            translated_value=translated_value,
        )


def _validate_same_tokens(
    source_value: str,
    translated_value: str,
    pattern: re.Pattern[str],
    error_code: str,
    casefold: bool = False,
) -> None:
    source_tokens = pattern.findall(source_value or "")
    translated_tokens = pattern.findall(translated_value or "")
    if casefold:
        source_tokens = [token.upper() for token in source_tokens]
        translated_tokens = [token.upper() for token in translated_tokens]
    if sorted(source_tokens) != sorted(translated_tokens):
        raise RuntimeError(error_code)


def _validate_same_number_shapes(field_name: str, source_value: str, translated_value: str) -> None:
    source_numbers = _read_normalized_number_tokens(source_value)
    translated_numbers = _read_normalized_number_tokens(translated_value)
    if Counter(source_numbers) != Counter(translated_numbers):
        raise RuntimeError(
            "API_DCX_GEMINI_ADMIN_TRANSLATION_NUMBER_MISMATCH:"
            f"field={field_name};"
            f"source_numbers={json.dumps(source_numbers, ensure_ascii=False)};"
            f"translated_numbers={json.dumps(translated_numbers, ensure_ascii=False)}"
        )


def _read_normalized_number_tokens(value: str) -> list[str]:
    return [
        normalized_token
        for normalized_token in (
            _normalize_number_token(token)
            for token in _NUMBER_PATTERN.findall(value or "")
        )
        if normalized_token != ""
    ]


def _normalize_number_token(value: str) -> str:
    normalized_digits = []
    for character in value or "":
        try:
            normalized_digits.append(str(unicodedata.digit(character)))
        except (TypeError, ValueError):
            continue
    return "".join(normalized_digits)
