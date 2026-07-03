"""
CONTEXT:
This file tests small pure-text helpers for routing inbound email and WhatsApp messages into
private DCX trade threads. The database-backed route itself is smoke-tested manually while these
unit tests keep the noisy provider reply-body cleanup predictable.
"""

from messages.dcx_inbound_cross_surface_reference_text import (
    build_dcx_cross_surface_routed_message_text,
    strip_dcx_cross_surface_reference_from_message_text,
)


def test_strips_email_reply_quote_boundary_from_routed_message_text() -> None:
    routed_text = strip_dcx_cross_surface_reference_from_message_text(
        message_text=(
            "#TC2 Esta es una noticia realmente excelente. Asi podremos hacer muchos negocios.\n"
            "Replying to chat@mail.dcxagent.ai on May 3, 2026, 1:56 PM\n"
            "From: chat@mail.dcxagent.ai\n"
            "Subject: DCX trade chat TC2\n"
            "New DCX trade chat message in TC2."
        ),
        reference_code="TC2",
    )

    assert routed_text == "Esta es una noticia realmente excelente. Asi podremos hacer muchos negocios."


def test_strips_email_header_quote_boundary_from_routed_message_text() -> None:
    routed_text = strip_dcx_cross_surface_reference_from_message_text(
        message_text=(
            "#TC2 Agreed on the revised shipment window.\n"
            "From: chat@mail.dcxagent.ai\n"
            "To: trader@example.com\n"
            "Subject: DCX trade chat TC2\n"
            "New DCX trade chat message in TC2."
        ),
        reference_code="TC2",
    )

    assert routed_text == "Agreed on the revised shipment window."


def test_preserves_user_authored_email_subject_and_body_without_email_metadata() -> None:
    routed_text = build_dcx_cross_surface_routed_message_text(
        message_subject="#TC2 Testing email replies",
        message_text=(
            "This is the body text.\n"
            "From: chat@mail.dcxagent.ai\n"
            "Subject: DCX trade chat TC2"
        ),
        reference_code="TC2",
        include_subject=True,
    )

    assert routed_text == "Testing email replies\n\nThis is the body text."


def test_drops_dcx_notification_subject_when_email_reply_subject_is_not_user_authored() -> None:
    routed_text = build_dcx_cross_surface_routed_message_text(
        message_subject="Re: DCX trade chat TC2",
        message_text="#TC2 Yes, that works.",
        reference_code="TC2",
        include_subject=True,
    )

    assert routed_text == "Yes, that works."


def test_strips_reference_and_footer_lines_from_routed_message_text() -> None:
    routed_text = strip_dcx_cross_surface_reference_from_message_text(
        message_text=(
            "#TC2 Yes, that works for us.\n"
            "Open in DCX: https://app.dcxagent.ai/trades/chats/2\n"
            "Reply with #TC2 followed by your message."
        ),
        reference_code="TC2",
    )

    assert routed_text == "Yes, that works for us."


def test_strips_reference_and_following_punctuation_from_routed_message_text() -> None:
    routed_text = strip_dcx_cross_surface_reference_from_message_text(
        message_text="#AI39, Correct, and China can afford to subsidise open source AI.",
        reference_code="AI39",
    )

    assert routed_text == "Correct, and China can afford to subsidise open source AI."
