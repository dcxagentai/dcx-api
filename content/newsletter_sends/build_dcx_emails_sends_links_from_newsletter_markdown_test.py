from content.newsletter_sends.build_dcx_emails_sends_links_from_newsletter_markdown import (
    build_dcx_emails_sends_links_from_newsletter_markdown,
)


def test_extracts_markdown_and_bare_links_in_original_order() -> None:
    payload = build_dcx_emails_sends_links_from_newsletter_markdown(
        """
        Read the [full write-up](https://dcxagent.ai/en/insights/full-report)
        and also visit https://dcxagent.ai/en/access for onboarding.
        """
    )

    assert payload == [
        {
            "original_url": "https://dcxagent.ai/en/insights/full-report",
            "link_label": "full write-up",
        },
        {
            "original_url": "https://dcxagent.ai/en/access",
            "link_label": "https://dcxagent.ai/en/access",
        },
    ]


def test_de_duplicates_identical_links_and_preserves_first_label() -> None:
    payload = build_dcx_emails_sends_links_from_newsletter_markdown(
        """
        [Primary CTA](https://dcxagent.ai/en/access)
        https://dcxagent.ai/en/access
        """
    )

    assert payload == [
        {
            "original_url": "https://dcxagent.ai/en/access",
            "link_label": "Primary CTA",
        }
    ]


def test_returns_empty_list_for_empty_markdown() -> None:
    assert build_dcx_emails_sends_links_from_newsletter_markdown("   ") == []
