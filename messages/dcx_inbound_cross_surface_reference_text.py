"""
CONTEXT:
This file owns the small text rules that make DCX cross-surface references usable across email,
WhatsApp, and the app.
It exists so private trade chats and private market-topic AI chats share one careful way to detect
portable reference codes and remove mail-client plumbing before messages become canonical turns.

CONTRACT:
- preconditions:
  - reference_prefix is one short alphabetic routing namespace such as `AI`, `TC`, `T`, `DM`, or `P`.
  - reference_code is one concrete reference such as `AI2`, `TC7`, `T3`, `DM4`, or `P9`.
  - message_subject and message_text may contain email/WhatsApp reply noise.
- postconditions:
  - Extracts exact namespace references without accepting arbitrary embedded words.
  - Removes reference codes, quoted email headers, prior reply blocks, and DCX footer lines.
  - Optionally preserves a user-authored email subject above the cleaned body text.
- side_effects: []
- idempotent: true
- retry_safe: true
- async: false

NARRATIVE:
WHY this exists:
  Traders should have one memorable rule for cross-surface continuity: include the visible reference
  code wherever they post from. The backend should then turn noisy provider text into the clean
  message that belongs in the product.
WHEN TO USE it:
  Use it from provider-origin routing capabilities before appending to a DCX conversation.
WHEN NOT TO USE it:
  Do not use it as an authorization check. Callers must still verify ownership or participation.
WHAT CAN GO WRONG:
  Email clients format quoted history differently, so this helper uses conservative cut points and
  leaves the rest of the authorization/routing work to callers.
WHAT COMES NEXT:
  Provider reply-id correlation can become a convenience fallback later while these explicit
  references stay as the supportable human contract.

TESTS:
- route_dcx_inbound_contact_message_to_trade_thread_if_applicable_test.py
- route_dcx_inbound_contact_message_to_market_topic_if_applicable_test.py

ERRORS:
- none

CODE:
"""

from __future__ import annotations

import re

EMAIL_REPLY_QUOTE_BOUNDARY_PATTERNS = [
    re.compile(r"^replying to .+", re.IGNORECASE),
    re.compile(r"^on .+ wrote:$", re.IGNORECASE),
    re.compile(r"^(from|to|cc|bcc|date|sent|subject):\s*.+", re.IGNORECASE),
]

DCX_CROSS_SURFACE_REFERENCE_PREFIX_BY_KIND = {
    "ai_chat": "AI",
    "trade_chat": "TC",
    "trade": "T",
    "dm": "DM",
    "feed_post": "P",
}


def extract_dcx_cross_surface_routing_reference(text: str) -> dict | None:
    normalized_text = _read_dcx_cross_surface_reference_detection_text(text)
    reference_matches = []
    for reference_kind, reference_prefix in sorted(
        DCX_CROSS_SURFACE_REFERENCE_PREFIX_BY_KIND.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    ):
        reference_match = _read_dcx_cross_surface_reference_match(
            normalized_text=normalized_text,
            reference_prefix=reference_prefix,
        )
        if reference_match is None:
            continue
        reference_id = read_dcx_cross_surface_reference_id(
            reference_code=reference_match["reference_code"],
            reference_prefix=reference_prefix,
        )
        if reference_id is None:
            continue
        reference_matches.append(
            {
                "reference_kind": reference_kind,
                "reference_prefix": reference_prefix,
                "reference_code": reference_match["reference_code"],
                "reference_id": reference_id,
                "match_start": reference_match["match_start"],
            }
        )
    if not reference_matches:
        return None

    earliest_reference = sorted(
        reference_matches,
        key=lambda item: (item["match_start"], -len(item["reference_prefix"])),
    )[0]
    return {
        "reference_kind": earliest_reference["reference_kind"],
        "reference_prefix": earliest_reference["reference_prefix"],
        "reference_code": earliest_reference["reference_code"],
        "reference_id": earliest_reference["reference_id"],
    }


def extract_dcx_cross_surface_reference_code(text: str, reference_prefix: str) -> str | None:
    normalized_text = _read_dcx_cross_surface_reference_detection_text(text)
    reference_match = _read_dcx_cross_surface_reference_match(
        normalized_text=normalized_text,
        reference_prefix=reference_prefix,
    )
    return None if reference_match is None else reference_match["reference_code"]


def _read_dcx_cross_surface_reference_match(
    normalized_text: str,
    reference_prefix: str,
) -> dict | None:
    normalized_prefix = reference_prefix.strip().upper() if isinstance(reference_prefix, str) else ""
    if not normalized_prefix.isalpha() or len(normalized_prefix) > 4:
        return None

    pattern = re.compile(
        rf"(?:^|[\s#])(?P<reference_prefix>{re.escape(normalized_prefix)})(?P<item_id>[0-9]{{1,12}})(?=\b)",
        re.IGNORECASE,
    )
    match = pattern.search(normalized_text)
    if match is None:
        return None
    return {
        "reference_code": f"{normalized_prefix}{match.group('item_id')}",
        "match_start": match.start("reference_prefix"),
    }


def _read_dcx_cross_surface_reference_detection_text(text: str) -> str:
    normalized_text = text if isinstance(text, str) else ""
    detection_lines = []
    for raw_line in normalized_text.splitlines():
        line = raw_line.strip()
        if line == "":
            continue
        if line.startswith(">") or _read_line_is_email_reply_quote_boundary(line):
            break
        if "open in dcx:" in line.lower() or "reply with #" in line.lower():
            continue
        detection_lines.append(line)
    return "\n".join(detection_lines)


def read_dcx_cross_surface_reference_id(reference_code: str, reference_prefix: str) -> int | None:
    normalized_reference_code = reference_code.strip().upper() if isinstance(reference_code, str) else ""
    normalized_prefix = reference_prefix.strip().upper() if isinstance(reference_prefix, str) else ""
    if normalized_prefix == "" or not normalized_reference_code.startswith(normalized_prefix):
        return None
    raw_id = normalized_reference_code[len(normalized_prefix):]
    if not raw_id.isdigit():
        return None
    reference_id = int(raw_id)
    return reference_id if reference_id > 0 else None


def build_dcx_cross_surface_routed_message_text(
    message_subject: str,
    message_text: str,
    reference_code: str,
    include_subject: bool,
) -> str:
    body_text = strip_dcx_cross_surface_reference_from_message_text(
        message_text=message_text,
        reference_code=reference_code,
    )
    if not include_subject:
        return body_text

    subject_text = strip_dcx_cross_surface_reference_from_subject(
        message_subject=message_subject,
        reference_code=reference_code,
    )
    if subject_text == "":
        return body_text
    if body_text == "":
        return subject_text
    if subject_text.lower() == body_text.lower():
        return body_text
    return f"{subject_text}\n\n{body_text}"


def strip_dcx_cross_surface_reference_from_message_text(message_text: str, reference_code: str) -> str:
    normalized_message_text = message_text.strip() if isinstance(message_text, str) else ""
    if normalized_message_text == "":
        return ""

    stripped_lines = []
    for raw_line in normalized_message_text.splitlines():
        line = raw_line.strip()
        if line == "":
            continue
        if line.startswith(">") or _read_line_is_email_reply_quote_boundary(line):
            break
        if "open in dcx:" in line.lower() or "reply with #" in line.lower():
            continue
        stripped_lines.append(line)

    stripped_text = "\n".join(stripped_lines)
    stripped_text = re.sub(
        rf"#?{re.escape(reference_code)}\b[\s,;:\-]*",
        "",
        stripped_text,
        flags=re.IGNORECASE,
    )
    stripped_text = re.sub(r"^[\s,;:\-]+", "", stripped_text)
    return stripped_text.strip()


def strip_dcx_cross_surface_reference_from_subject(message_subject: str, reference_code: str) -> str:
    normalized_subject = message_subject.strip() if isinstance(message_subject, str) else ""
    if normalized_subject == "":
        return ""

    while True:
        stripped_subject = re.sub(r"^(re|fw|fwd):\s*", "", normalized_subject, flags=re.IGNORECASE)
        if stripped_subject == normalized_subject:
            break
        normalized_subject = stripped_subject.strip()

    normalized_subject = re.sub(
        rf"#?{re.escape(reference_code)}\b",
        "",
        normalized_subject,
        flags=re.IGNORECASE,
    )
    normalized_subject = re.sub(r"\s+", " ", normalized_subject).strip(" #-:|")
    if normalized_subject.lower() in {
        "dcx trade chat",
        "trade chat",
        "dcx ai chat",
        "ai chat",
        "dcx market topic",
        "market topic",
        "dcx topic chat",
        "topic chat",
    }:
        return ""
    return normalized_subject


def _read_line_is_email_reply_quote_boundary(line: str) -> bool:
    normalized_line = line.strip() if isinstance(line, str) else ""
    if normalized_line == "":
        return False
    return any(pattern.match(normalized_line) is not None for pattern in EMAIL_REPLY_QUOTE_BOUNDARY_PATTERNS)
