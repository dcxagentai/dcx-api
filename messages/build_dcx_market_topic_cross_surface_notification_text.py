"""
CONTEXT:
This file builds the compact cross-surface notification text for one private DCX market topic.
It exists so initial topic creation and later `#T` topic-chat replies use the same WhatsApp/email
message shape instead of drifting across separate formatter blocks.

FLOW/SYSTEM:
- Inbound WhatsApp/email/app messages can create private market topics.
- Later WhatsApp/email replies can continue the topic with `#T{id}`.
- Both surfaces should show only the necessary topic reference, link, and AI message.

CONTRACT:
  preconditions:
    - market_topic_id is a positive persisted topic id.
    - route_reference_code is the visible topic reference such as `T18`.
    - message_text is the user-facing generated topic message.
    - topic_title may be empty for legacy callers, but should be present when available.
  postconditions:
    - Returns compact text in the shape:
      `#T18 Topic title`
      `https://app.../ai/chats/18`
      blank line
      message text
  side_effects: []
  idempotent: true
  retry_safe: true
  async: false

NARRATIVE:
  WHY this exists:
    - Traders reading WhatsApp/email need the least possible interface copy: topic reference, link, and
      the actual AI response.
  WHEN TO USE it:
    - Use it for outbound market-topic creation and topic-chat continuation notifications.
  WHEN NOT TO USE it:
    - Do not use it for trade candidates, trade-thread counterparty messages, or policy-blocked notices.
  WHAT CAN GO WRONG:
    - Missing titles make the reference line less descriptive, but the topic reference and URL still work.
  WHAT COMES NEXT:
    - If email later needs richer HTML, this plain-text builder should remain the canonical text fallback.

TESTS:
  - test_builds_compact_market_topic_cross_surface_notification_text

ERRORS: []

CODE:
"""

from __future__ import annotations

import re

from users.account_phone.dcx_whatsapp_phone_link_challenge_support import read_dcx_app_base_url


def build_dcx_market_topic_cross_surface_notification_text(
    market_topic_id: int,
    route_reference_code: str,
    topic_title: str,
    message_text: str,
    include_source_links: bool = True,
) -> str:
    normalized_reference_code = route_reference_code.strip().upper() if isinstance(route_reference_code, str) else ""
    normalized_topic_title = " ".join(topic_title.strip().split()) if isinstance(topic_title, str) else ""
    normalized_message_text = message_text.strip() if isinstance(message_text, str) else ""
    if include_source_links is False:
        normalized_message_text = read_dcx_market_topic_text_without_source_links(normalized_message_text)
    app_topic_url = f"{read_dcx_app_base_url().rstrip('/')}/ai/chats/{market_topic_id}"
    reference_line = f"#{normalized_reference_code}"
    if normalized_topic_title:
        reference_line = f"{reference_line} {normalized_topic_title}"

    return "\n".join(
        [
            reference_line,
            app_topic_url,
            "",
            normalized_message_text,
        ]
    ).strip()


def read_dcx_market_topic_text_without_source_links(message_text: str) -> str:
    lines = message_text.strip().splitlines()
    cleaned_lines = []
    in_sources_block = False
    for line in lines:
        if line.strip().lower() == "sources:":
            in_sources_block = True
            cleaned_lines.append(line)
            continue
        if in_sources_block:
            cleaned_line = re.sub(r"^- \[([^\]]+)\]\([^)]+\)\s*$", r"- \1", line.strip())
            cleaned_line = re.sub(r"^- ([^:]+):\s*https?://\S+\s*$", r"- \1", cleaned_line)
            cleaned_lines.append(cleaned_line)
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()
