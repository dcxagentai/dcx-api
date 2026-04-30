"""
CONTEXT:
This file sends one consolidated email outcome message for a processed DCX inbound message.
It exists so email traders receive one clear reply per input message, including mixed trade/topic
messages and non-trade outcomes.
"""

from __future__ import annotations

from apis.resend.send_email import (
    DCX_RESEND_SENDER_PROFILE_MESSAGES,
    send_email_via_resend,
)


def send_dcx_email_message_workflow_outcome_notification(
    recipient_email: str,
    subject: str,
    message_text: str,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - recipient_email is one canonical recipient email.
        - subject is one non-empty transactional subject line.
        - message_text is one non-empty consolidated workflow outcome body.
      postconditions:
        - Sends one conversational DCX email containing the whole message workflow outcome.
      side_effects:
        - sends one email through Resend using the conversational sender profile
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: caller owns deduplication because this function is a provider boundary

    NARRATIVE:
      WHY this exists:
        - Email-originated traders should receive one coherent answer telling them what DCX did with their message.
      WHEN TO USE it:
        - Use it after one email-originated contact message has completed workflow routing.
      WHEN NOT TO USE it:
        - Do not use it for app-originated sends or provider webhook ingestion.
      WHAT CAN GO WRONG:
        - Missing sender config or provider send failures can reject the email.
      WHAT COMES NEXT:
        - Slice 2 can add reply parsing and thread-aware email interaction flows.

    TESTS:
      - send_dcx_email_message_workflow_outcome_notification_test.py::test_sends_one_outcome_email
      - send_dcx_email_message_workflow_outcome_notification_test.py::test_rejects_blank_inputs

    ERRORS:
      - API_DCX_EMAIL_WORKFLOW_OUTCOME_MESSAGE_INVALID:
          suggested_action: Retry with a recipient email, subject, and message body.
          common_causes:
            - blank email
            - blank subject
            - blank message body
          recovery_steps:
            - Rebuild the email draft inputs.
            - Retry the send.
          retry_safe: true
      - API_DCX_EMAIL_WORKFLOW_OUTCOME_MESSAGE_SEND_FAILED:
          suggested_action: Confirm Resend configuration and retry when the provider is healthy.
          common_causes:
            - provider send failure
            - missing message-sender profile configuration
          recovery_steps:
            - Check Resend configuration and logs.
            - Retry later if duplicate delivery would be acceptable.
          retry_safe: false

    CODE:
    """
    if not isinstance(recipient_email, str) or recipient_email.strip() == "":
        raise RuntimeError("API_DCX_EMAIL_WORKFLOW_OUTCOME_MESSAGE_INVALID")
    if not isinstance(subject, str) or subject.strip() == "":
        raise RuntimeError("API_DCX_EMAIL_WORKFLOW_OUTCOME_MESSAGE_INVALID")
    if not isinstance(message_text, str) or message_text.strip() == "":
        raise RuntimeError("API_DCX_EMAIL_WORKFLOW_OUTCOME_MESSAGE_INVALID")

    try:
        return send_email_via_resend(
            email_delivery_draft={
                "recipient_email": recipient_email.strip(),
                "subject": subject.strip(),
                "text_body": message_text.strip(),
            },
            sender_profile=DCX_RESEND_SENDER_PROFILE_MESSAGES,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_EMAIL_WORKFLOW_OUTCOME_MESSAGE_SEND_FAILED") from exc
