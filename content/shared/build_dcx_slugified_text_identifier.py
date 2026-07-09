"""
CONTEXT:
This file builds one stable UTF-8 slug-like identifier from human-entered DCX content text.
It exists so content pages, categories, and newsletter drafts can derive readable internal keys
or public URL slugs without duplicating the same normalization rules across content capabilities.
"""

from __future__ import annotations

import re
import unicodedata

_DCX_SLUG_DUPLICATE_HYPHENS_PATTERN = re.compile(r"-+")


def build_dcx_slugified_text_identifier(value: str) -> str:
    """
    CONTRACT:
      preconditions:
        - value is one candidate human-readable text value.
      postconditions:
        - Returns a lowercase UTF-8 slug fragment suitable for one URL path segment.
        - Preserves Unicode letters, marks, and numbers for native-language slugs.
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
        - Unsupported punctuation, symbols, slashes, and control characters are converted to
          hyphen separators or removed.
      WHAT COMES NEXT:
        - Callers can append a short suffix when uniqueness is required.

    TESTS:
      - test_builds_ascii_slug_without_regression
      - test_preserves_latin_diacritics_for_utf8_urls
      - test_preserves_non_latin_native_script_slug_text
      - test_removes_url_structural_punctuation_from_one_path_segment

    ERRORS:
      - none:
          suggested_action: none
          common_causes: []
          recovery_steps: []
          retry_safe: true

    CODE:
    """
    normalized_input = unicodedata.normalize("NFKC", str(value or "").strip().lower())
    slug_characters = []
    previous_character_was_separator = False

    for character in normalized_input:
        if _is_dcx_slug_character_allowed(character):
            slug_characters.append(character)
            previous_character_was_separator = False
            continue

        if _is_dcx_slug_character_separator(character):
            if slug_characters and not previous_character_was_separator:
                slug_characters.append("-")
                previous_character_was_separator = True
            continue

    normalized = "".join(slug_characters)
    normalized = _DCX_SLUG_DUPLICATE_HYPHENS_PATTERN.sub("-", normalized).strip("-")
    return normalized or "item"


def _is_dcx_slug_character_allowed(character: str) -> bool:
    unicode_category = unicodedata.category(character)
    return unicode_category[0] in {"L", "M", "N"}


def _is_dcx_slug_character_separator(character: str) -> bool:
    if character.isspace():
        return True
    unicode_category = unicodedata.category(character)
    return unicode_category[0] in {"P", "S", "Z"}
