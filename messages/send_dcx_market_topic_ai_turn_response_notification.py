"""
CONTEXT:
This file sends one same-channel response for a market-topic AI chat turn that arrived from email
or WhatsApp.
It exists so a trader can continue a private DCX AI chat with `#AI` references without opening the
web app after every turn.

CONTRACT:
- preconditions:
  - market_topic_id identifies one market topic that the caller has already authorized.
  - route_reference_code is the visible chat reference such as `AI2`.
  - channel_type is `email` or `whatsapp`.
  - recipient_handle is the normalized verified address/phone that sent the inbound turn.
  - assistant_turn_text is non-empty.
- postconditions:
  - Sends at most one external provider message with the assistant response and reply instruction.
  - Returns provider status metadata for logging by the caller.
- side_effects:
  - may call Resend
  - may call Meta WhatsApp
- idempotent: false
- retry_safe: false unless duplicate provider messages are acceptable
- async: false

NARRATIVE:
WHY this exists:
  AI chats are private trader-to-AI workspaces. When a trader asks the next chat question
  from WhatsApp or email, the useful response should return to that same surface.
WHEN TO USE it:
  Use it after the canonical topic user turn and assistant turn have been saved.
WHEN NOT TO USE it:
  Do not use it for app-origin turns, public forum comments, or trader-to-trader trade chats.
WHAT CAN GO WRONG:
  Provider credentials, WhatsApp service windows, or email delivery can fail after the canonical
  AI turn has already been saved.
WHAT COMES NEXT:
  A queued delivery job can make this more resilient once webhook latency and LLM wait times need
  production-grade retries.

TESTS:
- route_dcx_inbound_contact_message_to_market_topic_if_applicable_test.py verifies injection points.

ERRORS:
- API_DCX_MARKET_TOPIC_AI_RESPONSE_NOTIFICATION_INVALID:
  suggested_action: Retry only after the route inputs are complete.
  common_causes: blank answer, unsupported channel, blank recipient
  recovery_steps: inspect routed contact message and topic turn rows.
  retry_safe: true
- API_DCX_MARKET_TOPIC_AI_RESPONSE_NOTIFICATION_SEND_FAILED:
  suggested_action: Keep the saved topic turns and retry only if duplicate delivery is acceptable.
  common_causes: provider outage, Meta service window, invalid provider configuration
  recovery_steps: inspect provider logs and send configuration.
  retry_safe: false

CODE:
"""

from __future__ import annotations

from emails.transactional.send_dcx_email_message_workflow_outcome_notification import (
    send_dcx_email_message_workflow_outcome_notification,
)
from apis.meta_whatsapp.send_dcx_whatsapp_message_workflow_outcome_notification import (
    send_dcx_whatsapp_message_workflow_outcome_notification,
)
from messages.build_dcx_market_topic_cross_surface_notification_text import (
    build_dcx_market_topic_cross_surface_notification_text,
    read_dcx_market_topic_text_without_source_links,
)


def send_dcx_market_topic_ai_turn_response_notification(
    market_topic_id: int,
    route_reference_code: str,
    topic_title: str,
    channel_type: str,
    recipient_handle: str,
    assistant_turn_text: str,
) -> dict:
    normalized_channel_type = channel_type.strip().lower() if isinstance(channel_type, str) else ""
    normalized_recipient_handle = recipient_handle.strip() if isinstance(recipient_handle, str) else ""
    normalized_reference_code = route_reference_code.strip().upper() if isinstance(route_reference_code, str) else ""
    normalized_assistant_turn_text = assistant_turn_text.strip() if isinstance(assistant_turn_text, str) else ""
    if (
        not isinstance(market_topic_id, int)
        or market_topic_id <= 0
        or normalized_reference_code == ""
        or normalized_channel_type not in {"email", "whatsapp"}
        or normalized_recipient_handle == ""
        or normalized_assistant_turn_text == ""
    ):
        raise RuntimeError("API_DCX_MARKET_TOPIC_AI_RESPONSE_NOTIFICATION_INVALID")

    assistant_text_for_surface = (
        _read_whatsapp_market_topic_assistant_text_without_source_links(normalized_assistant_turn_text)
        if normalized_channel_type == "whatsapp"
        else normalized_assistant_turn_text
    )
    message_text = _build_market_topic_ai_response_notification_text(
        market_topic_id=market_topic_id,
        route_reference_code=normalized_reference_code,
        topic_title=topic_title,
        assistant_turn_text=assistant_text_for_surface,
    )

    try:
        if normalized_channel_type == "email":
            provider_result = send_dcx_email_message_workflow_outcome_notification(
                recipient_email=normalized_recipient_handle,
                subject=f"DCX: {topic_title.strip() or normalized_reference_code}",
                message_text=message_text,
            )
            provider_type = "resend"
        else:
            provider_result = send_dcx_whatsapp_message_workflow_outcome_notification(
                phone_e164=normalized_recipient_handle,
                message_text=message_text,
            )
            provider_type = "meta_whatsapp"
    except Exception as exc:
        raise RuntimeError("API_DCX_MARKET_TOPIC_AI_RESPONSE_NOTIFICATION_SEND_FAILED") from exc

    return {
        "status": "sent",
        "channel_type": normalized_channel_type,
        "provider_type": provider_type,
        "provider_message_id": provider_result.get("provider_message_id"),
        "provider_result": provider_result,
    }


def _build_market_topic_ai_response_notification_text(
    market_topic_id: int,
    route_reference_code: str,
    topic_title: str,
    assistant_turn_text: str,
) -> str:
    return build_dcx_market_topic_cross_surface_notification_text(
        market_topic_id=market_topic_id,
        route_reference_code=route_reference_code,
        topic_title=topic_title,
        message_text=assistant_turn_text,
    )


def _read_whatsapp_market_topic_assistant_text_without_source_links(assistant_turn_text: str) -> str:
    return read_dcx_market_topic_text_without_source_links(assistant_turn_text)
