"""
CONTEXT:
This file maps one structured trade material string onto the simple commodity/material keys that
drive DCX MVP trade-interest alerts.
It exists so the first investor-proof alert slice can stay deterministic and auditable instead of
claiming full AI matching.

CONTRACT:
preconditions:
- material_text is the normalized or raw material text from a trade version.
- material_options can be omitted, in which case the built-in MVP option list is used.
postconditions:
- Returns one material_key when a configured synonym appears in the material text.
- Returns null when no simple MVP material match is found.
side_effects: []
idempotent: true
retry_safe: true
async: false

NARRATIVE:
WHY this exists:
  Interested-trade alerts need a transparent first matching rule: "aluminum-like text matches the
  aluminum interest." This is intentionally simpler than real commodity matching.
WHEN TO USE it:
  Use it before sending trade-interest alerts or in tests that need the same deterministic mapping.
WHEN NOT TO USE it:
  Do not use it as legal, commercial, sanctions, counterparty, or execution-grade matching.
WHAT CAN GO WRONG:
  Vague material text can fail to match, and broad synonyms can over-match. That is acceptable for
  the MVP slice because material options are visible and small.
WHAT COMES NEXT:
  Later slices can add commodity ontologies, aliases by language, user-specific filters, and
  trader-reviewed matching rules.

TESTS:
- read_dcx_trade_interest_material_key_test.py::test_matches_aluminum_ingots_to_aluminum_key
- read_dcx_trade_interest_material_key_test.py::test_returns_none_for_unknown_material

ERRORS:
- none; this helper fails closed by returning null for unsupported or unmatched input.

CODE:
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


DCX_DEFAULT_TRADE_INTEREST_MATERIAL_OPTIONS = [
    {
        "material_key": "aluminum",
        "synonyms": ["aluminium", "aluminum", "primary aluminum", "primary aluminium", "aluminum ingot", "aluminium ingot", "p1020a"],
    },
    {
        "material_key": "wheat",
        "synonyms": ["wheat", "milling wheat", "feed wheat", "durum"],
    },
    {
        "material_key": "urea",
        "synonyms": ["urea", "fertilizer urea", "fertiliser urea", "prilled urea", "granular urea"],
    },
    {
        "material_key": "copper",
        "synonyms": ["copper", "copper cathode", "copper concentrate"],
    },
    {
        "material_key": "livestock",
        "synonyms": ["livestock", "cattle", "cow", "cows", "calves", "dairy cattle"],
    },
    {
        "material_key": "crude_oil",
        "synonyms": ["crude", "crude oil", "brent", "wti"],
    },
    {
        "material_key": "lng",
        "synonyms": ["lng", "liquefied natural gas", "natural gas"],
    },
    {
        "material_key": "sugar",
        "synonyms": ["sugar", "raw sugar", "white sugar", "icumsa"],
    },
    {
        "material_key": "coffee",
        "synonyms": ["coffee", "arabica", "robusta"],
    },
    {
        "material_key": "soybeans",
        "synonyms": ["soybean", "soybeans", "soya", "soy meal", "soybean meal"],
    },
]


def read_dcx_trade_interest_material_key(
    material_text: str | None,
    material_options: list[dict[str, Any]] | None = None,
) -> str | None:
    normalized_material_text = _normalize_match_text(material_text)
    if normalized_material_text == "":
        return None

    for material_option in material_options or DCX_DEFAULT_TRADE_INTEREST_MATERIAL_OPTIONS:
        material_key = str(material_option.get("material_key") or "").strip().lower()
        if material_key == "":
            continue
        synonyms = material_option.get("synonyms")
        if not isinstance(synonyms, list):
            synonyms = material_option.get("synonyms_json")
        if not isinstance(synonyms, list):
            synonyms = []
        for synonym in synonyms:
            normalized_synonym = _normalize_match_text(str(synonym or ""))
            if normalized_synonym == "":
                continue
            if re.search(rf"(^|\W){re.escape(normalized_synonym)}(\W|$)", normalized_material_text):
                return material_key

    return None


def _normalize_match_text(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    normalized_value = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_value).strip()
