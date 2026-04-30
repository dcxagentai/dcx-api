"""
CONTEXT:
This file sends one short WhatsApp follow-up message asking the trader to review a trade candidate.
It exists so Slice 1 can nudge WhatsApp-originated traders back into the canonical app confirmation
surface without waiting for full WhatsApp button/reply parsing in Slice 2.
"""

from __future__ import annotations

from apis.meta_whatsapp.send_dcx_whatsapp_text_message import send_dcx_whatsapp_text_message


def send_dcx_whatsapp_trade_candidate_confirmation_message(
    phone_e164: str,
    trade_summary_text: str,
    trade_review_url: str,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - phone_e164 is one normalized E.164 phone number.
        - trade_summary_text is one short trade candidate summary.
        - trade_review_url is one full authenticated DCX app URL.
      postconditions:
        - Sends one WhatsApp text follow-up pointing the trader to the app review surface.
      side_effects:
        - sends one WhatsApp text message through the configured Meta account
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - Traders who initiate via WhatsApp still need a clear path into the new trade-confirmation workflow.
      WHEN TO USE it:
        - Use it after creating one trade candidate from a WhatsApp-originated message.
      WHEN NOT TO USE it:
        - Do not use it for prohibited messages or fully confirmed trades.
      WHAT CAN GO WRONG:
        - The provider can reject the follow-up send or the conversation window may be closed.
      WHAT COMES NEXT:
        - Later WhatsApp-specific button and reply parsing flows can replace this simple nudge.

    TESTS:
      - none yet

    ERRORS:
      - API_DCX_WHATSAPP_TRADE_CONFIRMATION_MESSAGE_INVALID:
          suggested_action: Retry with a normalized phone number, non-empty summary, and valid review URL.
          common_causes:
            - blank phone
            - blank summary
            - blank review URL
          recovery_steps:
            - Rebuild the notification payload.
            - Retry the send.
          retry_safe: true
      - API_DCX_WHATSAPP_TRADE_CONFIRMATION_MESSAGE_SEND_FAILED:
          suggested_action: Confirm the Meta configuration and conversation window, then retry only if safe.
          common_causes:
            - provider rejection
            - missing WhatsApp provider configuration
          recovery_steps:
            - Check Meta provider logs.
            - Retry only if sending another message is acceptable.
          retry_safe: false

    CODE:
    """
    if not isinstance(phone_e164, str) or phone_e164.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_TRADE_CONFIRMATION_MESSAGE_INVALID")
    if not isinstance(trade_summary_text, str) or trade_summary_text.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_TRADE_CONFIRMATION_MESSAGE_INVALID")
    if not isinstance(trade_review_url, str) or trade_review_url.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_TRADE_CONFIRMATION_MESSAGE_INVALID")

    try:
        return send_dcx_whatsapp_text_message(
            phone_e164=phone_e164.strip(),
            message_text=(
                "We extracted a trade candidate from your message.\n"
                f"{trade_summary_text.strip()}\n"
                f"Review and confirm it in DCX: {trade_review_url.strip()}"
            ),
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_WHATSAPP_TRADE_CONFIRMATION_MESSAGE_SEND_FAILED") from exc
