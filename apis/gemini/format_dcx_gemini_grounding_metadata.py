"""
CONTEXT:
This file normalizes Gemini Google Search grounding metadata and formats source links for DCX
market-topic AI responses.
It exists so topic seed responses and later topic-chat responses share one source formatting path.

FLOW/SYSTEM:
- Gemini can use the built-in Google Search tool for topic seed and topic chat calls.
- Gemini returns normal response text plus optional grounding metadata.
- DCX stores markdown links for app/email rendering and strips links for WhatsApp delivery elsewhere.

CONTRACT:
  preconditions:
    - response_or_metadata may be a Google GenAI SDK object, a pydantic object, a dict, or null.
  postconditions:
    - Returns canonical grounding metadata with `web_search_queries` and `sources`.
    - Appends a markdown `Sources:` block when source links exist.
  side_effects: []
  idempotent: true
  retry_safe: true
  async: false

NARRATIVE:
  WHY this exists:
    - Source formatting should not drift between the first AI response and later topic-chat responses.
  WHEN TO USE it:
    - Use it immediately after Gemini topic calls that may have Google Search grounding metadata.
  WHEN NOT TO USE it:
    - Do not use it for raw file-analysis citations or provider logs that need full unnormalized payloads.
  WHAT CAN GO WRONG:
    - Grounding metadata shape can vary by SDK/model version, so unknown shapes normalize to `{}`.
  WHAT COMES NEXT:
    - Later UI can render `grounding_metadata.sources` as dedicated source chips instead of text.

TESTS:
  - Covered through topic prompt contract tests.

ERRORS: []

CODE:
"""

from __future__ import annotations

from typing import Any


def read_dcx_gemini_response_grounding_metadata(response: Any) -> dict:
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return {}
    grounding_metadata = getattr(candidates[0], "grounding_metadata", None)
    return _model_dump_or_dict(grounding_metadata)


def normalize_dcx_gemini_grounding_metadata(value: Any) -> dict:
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


def append_dcx_grounding_sources_to_assistant_text(assistant_turn_text: str, grounding_metadata: dict) -> str:
    sources = grounding_metadata.get("sources") if isinstance(grounding_metadata, dict) else []
    if not isinstance(sources, list) or not sources:
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
    assistant_text_without_sources = _strip_existing_sources_block(assistant_turn_text)
    return f"{assistant_text_without_sources.strip()}\n\nSources:\n{chr(10).join(source_lines)}"


def _strip_existing_sources_block(value: str) -> str:
    lines = value.strip().splitlines()
    for line_index in range(len(lines) - 1, -1, -1):
        if lines[line_index].strip().lower() == "sources:":
            return "\n".join(lines[:line_index]).strip()
    return value.strip()


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
