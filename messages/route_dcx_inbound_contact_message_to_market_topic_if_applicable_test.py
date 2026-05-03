"""
CONTEXT:
This file tests the small deterministic text behavior for cross-surface market-topic routing.
Database-backed owner checks and Gemini/provider calls are exercised through smoke paths; these
tests keep the #T reference contract and routed text cleanup stable.
"""

from messages.dcx_inbound_cross_surface_reference_text import (
    build_dcx_cross_surface_routed_message_text,
)
from messages.route_dcx_inbound_contact_message_to_market_topic_if_applicable import (
    _extract_market_topic_reference_code,
)
from messages.send_dcx_market_topic_ai_turn_response_notification import (
    _build_market_topic_ai_response_notification_text,
    _read_whatsapp_market_topic_assistant_text_without_source_links,
)


def test_extracts_market_topic_reference_from_subject_or_body() -> None:
    assert _extract_market_topic_reference_code("Re: DCX market topic T42") == "T42"
    assert _extract_market_topic_reference_code("#t7 What are the price drivers?") == "T7"
    assert _extract_market_topic_reference_code("No topic reference here") is None


def test_builds_clean_routed_market_topic_email_text_with_subject_and_body() -> None:
    routed_text = build_dcx_cross_surface_routed_message_text(
        message_subject="#T2 Aluminum premiums",
        message_text=(
            "#T2 What changed this week?\n"
            "From: chat@mail.dcxagent.ai\n"
            "To: trader@example.com\n"
            "Subject: DCX market topic T2"
        ),
        reference_code="T2",
        include_subject=True,
    )

    assert routed_text == "Aluminum premiums\n\nWhat changed this week?"


def test_builds_same_channel_ai_response_with_topic_reference_instruction(monkeypatch) -> None:
    monkeypatch.setenv("DCX_APP_BASE_URL", "https://app.dcxagent.ai")

    message_text = _build_market_topic_ai_response_notification_text(
        market_topic_id=2,
        route_reference_code="T2",
        topic_title="Aluminum premiums",
        assistant_turn_text="The main drivers are Chinese restocking and freight volatility.",
    )

    assert message_text == (
        "#T2 Aluminum premiums\n"
        "https://app.dcxagent.ai/me/topics/2\n\n"
        "The main drivers are Chinese restocking and freight volatility."
    )


def test_strips_source_links_from_whatsapp_topic_ai_response_text() -> None:
    assert _read_whatsapp_market_topic_assistant_text_without_source_links(
        "Latest report summary.\n\n"
        "Sources:\n"
        "- [UN](https://example.com/un)\n"
        "- Reuters: https://example.com/reuters"
    ) == (
        "Latest report summary.\n\n"
        "Sources:\n"
        "- UN\n"
        "- Reuters"
    )
