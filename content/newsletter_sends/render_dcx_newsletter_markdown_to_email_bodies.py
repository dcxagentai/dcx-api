"""
CONTEXT:
This file renders DCX newsletter markdown into email-safe text and HTML bodies.
It exists so the newsletter dispatch worker can send readable emails through Resend
without waiting for a richer templating or WYSIWYG system.
"""

from __future__ import annotations

import html
import re

_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
_BARE_URL_PATTERN = re.compile(r"https?://[^\s<>()]+")


def render_dcx_newsletter_markdown_to_email_bodies(
    markdown_text: str,
    tracked_url_by_original_url: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    CONTRACT:
      preconditions:
        - markdown_text is one newsletter body string and may be empty.
        - tracked_url_by_original_url is either null or maps original outbound URLs to send-specific links.
      postconditions:
        - Returns one `text_body` string suitable for plain-text email delivery.
        - Returns one `html_body` string suitable for HTML email delivery.
        - Preserves outbound links while optionally swapping them to tracked send-specific URLs.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Newsletter sending now needs one backend-owned markdown rendering path that is good enough
          for MVP delivery and consistent across worker runs.
      WHEN TO USE it:
        - Use it while dispatching one prepared newsletter recipient send.
      WHEN NOT TO USE it:
        - Do not use it for admin preview panels or for rich HTML authoring.
      WHAT CAN GO WRONG:
        - Markdown can be malformed.
        - Some richer markdown constructs are intentionally unsupported in this MVP renderer.
      WHAT COMES NEXT:
        - Later we can swap this renderer for a richer shared markdown/email pipeline while keeping
          the dispatch contract stable.

    TESTS:
      - renders_markdown_links_and_basic_formatting_for_email_delivery
      - swaps_original_urls_for_tracked_urls_when_present
      - returns_empty_wrappers_for_blank_markdown

    ERRORS:
      - none:
          suggested_action: none
          common_causes: []
          recovery_steps: []
          retry_safe: true

    CODE:
    """
    normalized_markdown = markdown_text.replace("\r\n", "\n").strip()
    if normalized_markdown == "":
        return {
            "text_body": "",
            "html_body": "<div></div>",
        }

    tracked_links = tracked_url_by_original_url or {}
    html_parts: list[str] = []
    text_parts: list[str] = []
    current_list_type: str | None = None
    current_text_list_index = 1

    def close_list() -> None:
        nonlocal current_list_type
        nonlocal current_text_list_index
        if current_list_type is not None:
            html_parts.append(f"</{current_list_type}>")
            current_list_type = None
            current_text_list_index = 1

    for raw_line in normalized_markdown.split("\n"):
        trimmed_line = raw_line.strip()

        if trimmed_line == "":
            close_list()
            if len(text_parts) > 0 and text_parts[-1] != "":
                text_parts.append("")
            continue

        unordered_match = re.match(r"^-\s+(.+)$", trimmed_line)
        if unordered_match:
            if current_list_type != "ul":
                close_list()
                current_list_type = "ul"
                html_parts.append("<ul>")
            item_body = unordered_match.group(1)
            html_parts.append(f"<li>{_render_inline_markdown_to_html(item_body, tracked_links)}</li>")
            text_parts.append(f"- {_render_inline_markdown_to_text(item_body, tracked_links)}")
            continue

        ordered_match = re.match(r"^\d+\.\s+(.+)$", trimmed_line)
        if ordered_match:
            if current_list_type != "ol":
                close_list()
                current_list_type = "ol"
                html_parts.append("<ol>")
            item_body = ordered_match.group(1)
            html_parts.append(f"<li>{_render_inline_markdown_to_html(item_body, tracked_links)}</li>")
            text_parts.append(f"{current_text_list_index}. {_render_inline_markdown_to_text(item_body, tracked_links)}")
            current_text_list_index += 1
            continue

        close_list()

        heading_level = 0
        heading_body = trimmed_line
        for prefix in ("##### ", "#### ", "### ", "## ", "# "):
            if trimmed_line.startswith(prefix):
                heading_level = prefix.count("#")
                heading_body = trimmed_line[len(prefix):]
                break

        if heading_level > 0:
            html_parts.append(
                f"<h{heading_level}>{_render_inline_markdown_to_html(heading_body, tracked_links)}</h{heading_level}>"
            )
            text_parts.append(_render_inline_markdown_to_text(heading_body, tracked_links))
            text_parts.append("")
            continue

        html_parts.append(f"<p>{_render_inline_markdown_to_html(trimmed_line, tracked_links)}</p>")
        text_parts.append(_render_inline_markdown_to_text(trimmed_line, tracked_links))
        text_parts.append("")

    close_list()

    while len(text_parts) > 0 and text_parts[-1] == "":
        text_parts.pop()

    return {
        "text_body": "\n".join(text_parts),
        "html_body": "<div>" + "\n".join(html_parts) + "</div>",
    }


def _render_inline_markdown_to_html(
    value: str,
    tracked_url_by_original_url: dict[str, str],
) -> str:
    escaped_value = html.escape(value)

    def replace_markdown_link(match: re.Match[str]) -> str:
        link_label = html.escape(match.group(1).strip() or match.group(2).strip())
        original_url = match.group(2).strip()
        target_url = html.escape(tracked_url_by_original_url.get(original_url, original_url), quote=True)
        return f'<a href="{target_url}" target="_blank" rel="noreferrer">{link_label}</a>'

    rendered_value = _MARKDOWN_LINK_PATTERN.sub(replace_markdown_link, escaped_value)
    rendered_value = _replace_bare_urls_in_html(rendered_value, tracked_url_by_original_url)
    rendered_value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered_value)
    rendered_value = re.sub(r"\*(.+?)\*", r"<em>\1</em>", rendered_value)
    rendered_value = re.sub(r"`(.+?)`", r"<code>\1</code>", rendered_value)
    return rendered_value


def _replace_bare_urls_in_html(
    value: str,
    tracked_url_by_original_url: dict[str, str],
) -> str:
    rendered_parts: list[str] = []
    current_position = 0

    for match in _BARE_URL_PATTERN.finditer(value):
        matched_url = match.group(0).rstrip(".,;:!?")
        if "<a href=" in value[max(0, match.start() - 15):match.start()]:
            continue
        rendered_parts.append(value[current_position:match.start()])
        target_url = html.escape(tracked_url_by_original_url.get(matched_url, matched_url), quote=True)
        visible_url = html.escape(matched_url)
        rendered_parts.append(f'<a href="{target_url}" target="_blank" rel="noreferrer">{visible_url}</a>')
        current_position = match.start() + len(matched_url)

    rendered_parts.append(value[current_position:])
    return "".join(rendered_parts)


def _render_inline_markdown_to_text(
    value: str,
    tracked_url_by_original_url: dict[str, str],
) -> str:
    rendered_value = value

    def replace_markdown_link(match: re.Match[str]) -> str:
        link_label = match.group(1).strip() or match.group(2).strip()
        original_url = match.group(2).strip()
        target_url = tracked_url_by_original_url.get(original_url, original_url)
        return f"{link_label}: {target_url}"

    rendered_value = _MARKDOWN_LINK_PATTERN.sub(replace_markdown_link, rendered_value)

    def replace_bare_url(match: re.Match[str]) -> str:
        original_url = match.group(0).strip().rstrip(".,;:!?")
        return tracked_url_by_original_url.get(original_url, original_url)

    rendered_value = _BARE_URL_PATTERN.sub(replace_bare_url, rendered_value)
    rendered_value = re.sub(r"\*\*(.+?)\*\*", r"\1", rendered_value)
    rendered_value = re.sub(r"\*(.+?)\*", r"\1", rendered_value)
    rendered_value = re.sub(r"`(.+?)`", r"\1", rendered_value)
    return rendered_value
