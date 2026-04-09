"""
CONTEXT:
This file builds one stable slug-like identifier from human-entered DCX content text.
It exists so content pages and newsletter drafts can derive readable internal keys or slugs
without duplicating the same normalization rules across multiple content capabilities.
"""

from __future__ import annotations

import re

_DCX_SLUG_UNSAFE_CHARACTERS_PATTERN = re.compile(r"[^a-z0-9]+")
_DCX_SLUG_DUPLICATE_HYPHENS_PATTERN = re.compile(r"-+")


def build_dcx_slugified_text_identifier(value: str) -> str:
    """
    CONTRACT:
      preconditions:
        - value is one candidate human-readable text value.
      postconditions:
        - Returns a lowercase ASCII-safe slug fragment.
        - Never returns an empty string; falls back to `item`.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Multiple content capabilities need a small, consistent way to normalize page titles and
          newsletter labels into stable slug fragments.
      WHEN TO USE it:
        - Use it when creating or updating content slugs or human-readable content keys.
      WHEN NOT TO USE it:
        - Do not use it for security-sensitive opaque tokens.
      WHAT CAN GO WRONG:
        - Non-ASCII characters are simplified aggressively.
      WHAT COMES NEXT:
        - Callers can append a short suffix when uniqueness is required.

    TESTS:
      - covered_indirectly_by_content_page_create_and_newsletter_create_tests

    ERRORS:
      - none:
          suggested_action: none
          common_causes: []
          recovery_steps: []
          retry_safe: true

    CODE:
    """
    normalized = _DCX_SLUG_UNSAFE_CHARACTERS_PATTERN.sub("-", value.strip().lower())
    normalized = _DCX_SLUG_DUPLICATE_HYPHENS_PATTERN.sub("-", normalized).strip("-")
    return normalized or "item"
