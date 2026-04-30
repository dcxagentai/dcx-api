"""
CONTEXT:
This file sends one consolidated WhatsApp outcome message for a processed DCX inbound message.
It exists so WhatsApp traders receive one clear result per input message instead of one reply per
created trade candidate.
"""

from __future__ import annotations

from apis.meta_whatsapp.send_dcx_whatsapp_text_message import send_dcx_whatsapp_text_message


def send_dcx_whatsapp_message_workflow_outcome_notification(
    phone_e164: str,
    message_text: str,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - phone_e164 is one normalized E.164 phone number.
        - message_text is one non-empty consolidated workflow outcome body.
      postconditions:
        - Sends one WhatsApp text follow-up for the whole processed inbound message.
      side_effects:
        - sends one WhatsApp text message through the configured Meta account
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: caller owns deduplication because this function is a provider boundary

    NARRATIVE:
      WHY this exists:
        - Traders should get one coherent WhatsApp answer telling them what DCX did with their message.
      WHEN TO USE it:
        - Use it after one email/WhatsApp-originated contact message has completed workflow routing.
      WHEN NOT TO USE it:
        - Do not use it for app-originated messages or low-level delivery/read receipts.
      WHAT CAN GO WRONG:
        - The provider can reject the send, configuration can be missing, or the conversation window can be closed.
      WHAT COMES NEXT:
        - Slice 2 can replace plain text links with richer WhatsApp buttons when interaction flows mature.

    TESTS:
      - send_dcx_whatsapp_message_workflow_outcome_notification_test.py::test_sends_one_outcome_text_message
      - send_dcx_whatsapp_message_workflow_outcome_notification_test.py::test_rejects_blank_inputs

    ERRORS:
      - API_DCX_WHATSAPP_WORKFLOW_OUTCOME_MESSAGE_INVALID:
          suggested_action: Retry with a normalized phone number and non-empty outcome message.
          common_causes:
            - blank phone
            - blank message
          recovery_steps:
            - Rebuild the notification payload.
            - Retry the send.
          retry_safe: true
      - API_DCX_WHATSAPP_WORKFLOW_OUTCOME_MESSAGE_SEND_FAILED:
          suggested_action: Confirm the Meta configuration and conversation window, then retry only if another message is acceptable.
          common_causes:
            - provider rejection
            - missing WhatsApp provider configuration
            - closed WhatsApp conversation window
          recovery_steps:
            - Check Meta provider logs.
            - Retry only if duplicate delivery would be acceptable.
          retry_safe: false

    CODE:
    """
    if not isinstance(phone_e164, str) or phone_e164.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_WORKFLOW_OUTCOME_MESSAGE_INVALID")
    if not isinstance(message_text, str) or message_text.strip() == "":
        raise RuntimeError("API_DCX_WHATSAPP_WORKFLOW_OUTCOME_MESSAGE_INVALID")

    try:
        return send_dcx_whatsapp_text_message(
            phone_e164=phone_e164.strip(),
            message_text=message_text.strip(),
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_WHATSAPP_WORKFLOW_OUTCOME_MESSAGE_SEND_FAILED") from exc
