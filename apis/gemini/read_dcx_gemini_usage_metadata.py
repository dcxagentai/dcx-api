"""
CONTEXT:
This file normalizes Google Gemini SDK usage metadata into the small token-accounting shape DCX needs.
It exists so each Gemini provider boundary can return usage data without coupling business logic to SDK objects.

FLOW/SYSTEM:
- Any Gemini call receives a provider response object.
- DCX extracts prompt, candidate, and total token counts where Gemini supplies them.
- Callers decide whether and how to persist the normalized usage event.

CONTRACT:
  preconditions:
    - response is a Gemini SDK response or a test double with an optional usage_metadata attribute.
  postconditions:
    - Returns canonical integer token counts and a metadata snapshot.
  side_effects: []
  idempotent: true
  retry_safe: true
  async: false

NARRATIVE:
  WHY this exists:
    - MVP token accounting should be provider-returned, basic, and consistent across prompts.
  WHEN TO USE it:
    - Use it inside Gemini provider boundaries immediately after generate_content returns.
  WHEN NOT TO USE it:
    - Do not estimate costs here or mutate user totals directly; persistence belongs to usage capabilities.
  WHAT CAN GO WRONG:
    - SDK versions can expose slightly different metadata attributes, so this reader is defensive.
  WHAT COMES NEXT:
    - Later versions can add cached token counts, billable units, costs, and per-model pricing.

TESTS:
  - covered by focused Gemini boundary compile and injected response smoke tests.

ERRORS: []

CODE:
"""

from __future__ import annotations

from typing import Any


def read_dcx_gemini_usage_metadata(response: Any) -> dict:
    usage_metadata = getattr(response, "usage_metadata", None)
    prompt_token_count = _coerce_non_negative_int(
        _read_metadata_value(usage_metadata, "prompt_token_count")
    )
    candidates_token_count = _coerce_non_negative_int(
        _read_metadata_value(usage_metadata, "candidates_token_count")
    )
    total_token_count = _coerce_non_negative_int(
        _read_metadata_value(usage_metadata, "total_token_count")
    )

    return {
        "prompt_token_count": prompt_token_count,
        "candidates_token_count": candidates_token_count,
        "total_token_count": total_token_count,
        "cached_content_token_count": _coerce_non_negative_int(
            _read_metadata_value(usage_metadata, "cached_content_token_count")
        ),
        "thoughts_token_count": _coerce_non_negative_int(
            _read_metadata_value(usage_metadata, "thoughts_token_count")
        ),
    }


def _read_metadata_value(usage_metadata: Any, key: str) -> Any:
    if usage_metadata is None:
        return 0
    if isinstance(usage_metadata, dict):
        return usage_metadata.get(key, 0)
    return getattr(usage_metadata, key, 0)


def _coerce_non_negative_int(value: Any) -> int:
    try:
        coerced = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(coerced, 0)
