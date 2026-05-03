"""
CONTEXT:
This file tests small pure-text helpers for routing inbound email and WhatsApp messages into
private DCX trade threads. The database-backed route itself is smoke-tested manually while these
unit tests keep the noisy provider reply-body cleanup predictable.
"""

from messages.route_dcx_inbound_contact_message_to_trade_thread_if_applicable import (
    _build_routed_trade_thread_message_text,
    _strip_trade_thread_reference_from_message_text,
)


def test_strips_email_reply_quote_boundary_from_routed_message_text() -> None:
    routed_text = _strip_trade_thread_reference_from_message_text(
        message_text=(
            "#C2 Esta es una noticia realmente excelente. Asi podremos hacer muchos negocios.\n"
            "Replying to chat@mail.dcxagent.ai on May 3, 2026, 1:56 PM\n"
            "From: chat@mail.dcxagent.ai\n"
            "Subject: DCX trade chat C2\n"
            "New DCX trade chat message in C2."
        ),
        thread_reference_code="C2",
    )

    assert routed_text == "Esta es una noticia realmente excelente. Asi podremos hacer muchos negocios."


def test_strips_email_header_quote_boundary_from_routed_message_text() -> None:
    routed_text = _strip_trade_thread_reference_from_message_text(
        message_text=(
            "#C2 Agreed on the revised shipment window.\n"
            "From: chat@mail.dcxagent.ai\n"
            "To: trader@example.com\n"
            "Subject: DCX trade chat C2\n"
            "New DCX trade chat message in C2."
        ),
        thread_reference_code="C2",
    )

    assert routed_text == "Agreed on the revised shipment window."


def test_preserves_user_authored_email_subject_and_body_without_email_metadata() -> None:
    routed_text = _build_routed_trade_thread_message_text(
        message_subject="#C2 Testing email replies",
        message_text=(
            "This is the body text.\n"
            "From: chat@mail.dcxagent.ai\n"
            "Subject: DCX trade chat C2"
        ),
        thread_reference_code="C2",
        include_subject=True,
    )

    assert routed_text == "Testing email replies\n\nThis is the body text."


def test_drops_dcx_notification_subject_when_email_reply_subject_is_not_user_authored() -> None:
    routed_text = _build_routed_trade_thread_message_text(
        message_subject="Re: DCX trade chat C2",
        message_text="#C2 Yes, that works.",
        thread_reference_code="C2",
        include_subject=True,
    )

    assert routed_text == "Yes, that works."


def test_strips_reference_and_footer_lines_from_routed_message_text() -> None:
    routed_text = _strip_trade_thread_reference_from_message_text(
        message_text=(
            "#C2 Yes, that works for us.\n"
            "Open in DCX: https://app.dcxagent.ai/me/trade-threads/2\n"
            "Reply with #C2 followed by your message."
        ),
        thread_reference_code="C2",
    )

    assert routed_text == "Yes, that works for us."
