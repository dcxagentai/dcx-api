"""
CONTEXT:
This file sends one email follow-up asking the trader to review a trade candidate in the app.
It exists so Slice 1 can give email-originated traders the same basic confirmation path as app and
WhatsApp without waiting for full reply parsing.
"""

from __future__ import annotations

from apis.resend.send_email import (
    DCX_RESEND_SENDER_PROFILE_MESSAGES,
    send_email_via_resend,
)


def send_dcx_email_trade_candidate_confirmation_message(
    recipient_email: str,
    trade_summary_text: str,
    trade_review_url: str,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - recipient_email is one canonical recipient email.
        - trade_summary_text is one short trade candidate summary.
        - trade_review_url is one full authenticated DCX app URL.
      postconditions:
        - Sends one conversational DCX email asking the trader to review the trade candidate in the app.
      side_effects:
        - sends one email through Resend using the conversational sender profile
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - Traders who initiate via email should get the same basic review handoff into the app trade-confirmation surface.
      WHEN TO USE it:
        - Use it after creating one trade candidate from an email-originated message.
      WHEN NOT TO USE it:
        - Do not use it for prohibited messages or already confirmed trades.
      WHAT CAN GO WRONG:
        - Missing sender config or provider send failures can reject the email.
      WHAT COMES NEXT:
        - Later DCX can track these confirmation emails more richly and parse structured replies if we decide to.

    TESTS:
      - none yet

    ERRORS:
      - API_DCX_EMAIL_TRADE_CONFIRMATION_MESSAGE_INVALID:
          suggested_action: Retry with a real recipient email, summary, and trade review URL.
          common_causes:
            - blank email
            - blank summary
            - blank review URL
          recovery_steps:
            - Rebuild the email draft inputs.
            - Retry the send.
          retry_safe: true
      - API_DCX_EMAIL_TRADE_CONFIRMATION_MESSAGE_SEND_FAILED:
          suggested_action: Confirm Resend configuration and retry when the provider is healthy.
          common_causes:
            - provider send failure
            - missing message-sender profile configuration
          recovery_steps:
            - Check Resend configuration and logs.
            - Retry later.
          retry_safe: false

    CODE:
    """
    if not isinstance(recipient_email, str) or recipient_email.strip() == "":
        raise RuntimeError("API_DCX_EMAIL_TRADE_CONFIRMATION_MESSAGE_INVALID")
    if not isinstance(trade_summary_text, str) or trade_summary_text.strip() == "":
        raise RuntimeError("API_DCX_EMAIL_TRADE_CONFIRMATION_MESSAGE_INVALID")
    if not isinstance(trade_review_url, str) or trade_review_url.strip() == "":
        raise RuntimeError("API_DCX_EMAIL_TRADE_CONFIRMATION_MESSAGE_INVALID")

    try:
        return send_email_via_resend(
            email_delivery_draft={
                "recipient_email": recipient_email.strip(),
                "subject": "Review your DCX trade candidate",
                "text_body": (
                    "We extracted a trade candidate from your message.\n\n"
                    f"{trade_summary_text.strip()}\n\n"
                    f"Review and confirm it in DCX: {trade_review_url.strip()}"
                ),
            },
            sender_profile=DCX_RESEND_SENDER_PROFILE_MESSAGES,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_EMAIL_TRADE_CONFIRMATION_MESSAGE_SEND_FAILED") from exc
