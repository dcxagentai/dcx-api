"""
CONTEXT:
This file extracts one normalized list of outbound links from newsletter markdown for the DCX
email-send preparation system. It exists so prepared sends can snapshot the links that will later
be wrapped in tracked redirect URLs without depending on the provider-send step.
"""

from __future__ import annotations

import re

_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BARE_URL_PATTERN = re.compile(r"https?://[^\s<>()]+")


def build_dcx_emails_sends_links_from_newsletter_markdown(markdown_text: str) -> list[dict]:
    """
    CONTRACT:
      preconditions:
        - markdown_text is one newsletter body string and may be empty.
      postconditions:
        - Returns one de-duplicated ordered list of outbound HTTP/HTTPS links extracted from the body.
        - Each returned row contains `original_url` and `link_label`.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - One prepared newsletter send needs to know which links exist before the actual provider
          dispatch or click-tracking redirect step is connected.
      WHEN TO USE it:
        - Use it while preparing one newsletter send from the current live markdown body.
      WHEN NOT TO USE it:
        - Do not use it for rich-text HTML parsing or provider webhook payloads.
      WHAT CAN GO WRONG:
        - Markdown can contain malformed links.
        - Duplicate links can appear several times in the body.
      WHAT COMES NEXT:
        - The extracted links are stored in `stephen_dcx_emails_sends_links` with generated tracking tokens.

    TESTS:
      - extracts_markdown_and_bare_links_in_original_order
      - de_duplicates_identical_links_and_preserves_first_label
      - returns_empty_list_for_empty_markdown

    ERRORS:
      - none:
          suggested_action: none
          common_causes: []
          recovery_steps: []
          retry_safe: true

    CODE:
    """
    if markdown_text.strip() == "":
        return []

    collected_links: list[dict] = []
    seen_urls: set[str] = set()
    sanitized_text = markdown_text

    for match in _MARKDOWN_LINK_PATTERN.finditer(markdown_text):
        link_label = match.group(1).strip() or match.group(2).strip()
        original_url = match.group(2).strip()
        if original_url not in seen_urls:
            collected_links.append(
                {
                    "original_url": original_url,
                    "link_label": link_label,
                }
            )
            seen_urls.add(original_url)

        start, end = match.span()
        sanitized_text = sanitized_text[:start] + (" " * (end - start)) + sanitized_text[end:]

    for match in _BARE_URL_PATTERN.finditer(sanitized_text):
        original_url = match.group(0).strip().rstrip(".,;:!?")
        if original_url == "" or original_url in seen_urls:
            continue
        collected_links.append(
            {
                "original_url": original_url,
                "link_label": original_url,
            }
        )
        seen_urls.add(original_url)

    return collected_links
