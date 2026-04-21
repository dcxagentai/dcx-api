from content.newsletter_sends.render_dcx_newsletter_markdown_to_email_bodies import (
    render_dcx_newsletter_markdown_to_email_bodies,
)


def test_renders_markdown_links_and_basic_formatting_for_email_delivery() -> None:
    payload = render_dcx_newsletter_markdown_to_email_bodies(
        "# Weekly update\n\nHello **team**.\n\n- Read [Market note](https://dcxagent.ai/market)\n- Visit https://dcxagent.ai/app",
    )

    assert "Weekly update" in payload["text_body"]
    assert "Market note: https://dcxagent.ai/market" in payload["text_body"]
    assert '<strong>team</strong>' in payload["html_body"]
    assert '<a href="https://dcxagent.ai/market"' in payload["html_body"]
    assert '<a href="https://dcxagent.ai/app"' in payload["html_body"]


def test_swaps_original_urls_for_tracked_urls_when_present() -> None:
    payload = render_dcx_newsletter_markdown_to_email_bodies(
        "Read [Market note](https://dcxagent.ai/market)",
        tracked_url_by_original_url={
            "https://dcxagent.ai/market": "https://api.dcxagent.ai/email-links/token-123",
        },
    )

    assert "https://api.dcxagent.ai/email-links/token-123" in payload["text_body"]
    assert 'href="https://api.dcxagent.ai/email-links/token-123"' in payload["html_body"]


def test_returns_empty_wrappers_for_blank_markdown() -> None:
    payload = render_dcx_newsletter_markdown_to_email_bodies("   ")

    assert payload == {
        "text_body": "",
        "html_body": "<div></div>",
    }
