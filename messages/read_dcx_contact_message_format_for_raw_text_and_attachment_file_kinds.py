"""
CONTEXT:
This file determines the canonical DCX message_format for one stored message after raw text and
attachment file kinds are known.
It exists so app, email, and WhatsApp intake flows all classify mixed-format messages in the same
way before richer intent classification arrives later.
"""

from __future__ import annotations


def read_dcx_contact_message_format_for_raw_text_and_attachment_file_kinds(
    raw_text_content: str,
    attachment_file_kinds: list[str] | None,
    fallback_message_format: str | None = None,
) -> str:
    """
    CONTRACT:
      preconditions:
        - raw_text_content is one message-level raw text body or caption string.
        - attachment_file_kinds contains zero or more normalized DCX file kinds.
      postconditions:
        - Returns one canonical DCX message_format value.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The Messages inbox filters should stay consistent even when one message contains text and
          one or more attachments from different channels.
      WHEN TO USE it:
        - Use it after attachment validation and before or after the message row is finalized.
      WHEN NOT TO USE it:
        - Do not use it as the later business-intent classifier.
      WHAT CAN GO WRONG:
        - Unsupported file kinds may be ignored if callers do not validate first.
      WHAT COMES NEXT:
        - Later classifiers can use this coarse message_format as just one routing signal.

    TESTS:
      - covered indirectly by app-create, email-ingest, and WhatsApp-ingest tests

    ERRORS:
      - none

    CODE:
    """
    normalized_raw_text = raw_text_content.strip() if isinstance(raw_text_content, str) else ""
    normalized_attachment_file_kinds = [
        attachment_file_kind
        for attachment_file_kind in (attachment_file_kinds or [])
        if attachment_file_kind in {"image", "audio", "document"}
    ]
    unique_attachment_file_kinds = sorted(set(normalized_attachment_file_kinds))

    if len(unique_attachment_file_kinds) == 0:
        if fallback_message_format in {"text", "image", "audio", "document", "mixed"}:
            return fallback_message_format
        return "text"

    if len(unique_attachment_file_kinds) == 1 and normalized_raw_text == "":
        return unique_attachment_file_kinds[0]

    return "mixed"
