from messages.process_stored_dcx_contact_message_analysis import (
    _build_message_workflow_outcome_notification_payload,
)


def test_builds_one_consolidated_workflow_outcome_for_mixed_email_message(monkeypatch) -> None:
    monkeypatch.setenv("DCX_APP_BASE_URL", "https://app.dcxagent.ai")

    payload = _build_message_workflow_outcome_notification_payload(
        message_id=44,
        message_input={
            "channel_type": "email",
            "source_handle_normalized": "trader@example.com",
        },
        analysis_result={
            "moderation_status": "allowed",
        },
        analysis_run_status="completed",
        workflow_projection_result={
            "trade_outputs": [
                {
                    "trade_id": 12,
                    "title": "Urea offer",
                    "summary": "Offer for 200 MT urea CFR Tema for June.",
                }
            ],
            "market_topic_outputs": [
                {
                    "market_topic_id": 7,
                    "title": "Sanctions impact on fertilizer shipping to Ghana",
                    "summary": "Inquiry about sanctions and shipping.",
                }
            ],
            "other_outputs": [],
            "projection_errors": [],
        },
    )

    assert payload == {
        "message_id": 44,
        "channel_type": "email",
        "recipient_handle": "trader@example.com",
        "subject": "DCX found trades and market topics",
        "message_text": (
            "DCX processed your message.\n\n"
            "Trade candidates:\n"
            "Offer for 200 MT urea CFR Tema for June.\n"
            "Review: https://app.dcxagent.ai/me/trades/12\n\n"
            "Market topics:\n"
            "#T7 Sanctions impact on fertilizer shipping to Ghana\n"
            "Open: https://app.dcxagent.ai/me/topics/7\n"
            "Reply with #T7 followed by your question."
        ),
        "trade_ids": [12],
        "market_topic_ids": [7],
    }


def test_builds_policy_blocked_workflow_outcome_for_prohibited_whatsapp_message() -> None:
    payload = _build_message_workflow_outcome_notification_payload(
        message_id=45,
        message_input={
            "channel_type": "whatsapp",
            "source_handle_normalized": "+34600000001",
        },
        analysis_result={
            "moderation_status": "prohibited",
        },
        analysis_run_status="completed",
        workflow_projection_result={
            "trade_outputs": [],
            "market_topic_outputs": [],
            "other_outputs": [],
            "projection_errors": [],
        },
    )

    assert payload == {
        "message_id": 45,
        "channel_type": "whatsapp",
        "recipient_handle": "+34600000001",
        "subject": "DCX message blocked",
        "message_text": (
            "We received your message, but it was blocked by DCX content policy.\n\n"
            "It has not been routed into a trade or market topic workflow."
        ),
        "trade_ids": [],
        "market_topic_ids": [],
    }


def test_skips_workflow_outcome_notification_for_app_originated_message() -> None:
    payload = _build_message_workflow_outcome_notification_payload(
        message_id=46,
        message_input={
            "channel_type": "app",
            "source_handle_normalized": "",
        },
        analysis_result={
            "moderation_status": "allowed",
        },
        analysis_run_status="completed",
        workflow_projection_result={
            "trade_outputs": [],
            "market_topic_outputs": [],
            "other_outputs": [
                {
                    "workflow_item_id": 3,
                    "title": "Personal reminder",
                    "summary": "Personal message.",
                }
            ],
            "projection_errors": [],
        },
    )

    assert payload is None
