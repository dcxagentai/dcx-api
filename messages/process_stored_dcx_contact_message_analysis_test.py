from messages import process_stored_dcx_contact_message_analysis as module_under_test
from messages.process_stored_dcx_contact_message_analysis import (
    _build_message_workflow_outcome_notification_payload,
)


class _FakeWorkflowProjectionCursor:
    def __init__(self) -> None:
        self.executed_statements = []
        self.returning_rows = []

    def execute(self, query: str, params=None) -> None:
        self.executed_statements.append((query, params))
        if "INSERT INTO stephen_dcx_message_workflow_items" in query:
            self.returning_rows.append((701,))
        if "INSERT INTO stephen_dcx_market_topics" in query:
            self.returning_rows.append((55,))

    def fetchone(self):
        if not self.returning_rows:
            raise AssertionError("No fake RETURNING row was queued for this cursor fetch.")
        return self.returning_rows.pop(0)


def test_rebuild_market_topic_projection_uses_supplied_database_connect_for_usage_recording(monkeypatch) -> None:
    captured_usage_events = []
    supplied_connect = lambda **kwargs: None

    monkeypatch.setattr(
        module_under_test,
        "generate_dcx_gemini_structured_market_topic_seed",
        lambda **kwargs: {
            "provider_name": "google_gemini",
            "model_name": "gemini-test",
            "prompt_version": "topic-seed-test",
            "usage_metadata": {"total_token_count": 42},
            "topic_title": "Oil market volatility",
            "topic_summary_text": "Oil prices remain elevated after geopolitical disruption.",
            "topic_scope_text": "Follow oil-market impacts for traders.",
            "topic_tags": ["oil", "shipping"],
            "opening_ai_response_text": "Oil markets remain sensitive to supply risk.",
            "grounding_metadata": {},
            "raw_output_json": {"topic_title": "Oil market volatility"},
        },
    )
    monkeypatch.setattr(
        module_under_test,
        "_record_best_effort_llm_usage_event",
        lambda **kwargs: captured_usage_events.append(kwargs),
    )
    monkeypatch.setattr(
        module_under_test,
        "_record_best_effort_activity_event",
        lambda **kwargs: None,
    )

    result = module_under_test._rebuild_message_workflow_projections(
        cursor=_FakeWorkflowProjectionCursor(),
        message_id=115,
        message_input={
            "message_id": 115,
            "channel_type": "app",
            "provider_type": "dcx_app",
            "message_subject": "Oil market note",
            "raw_text_content": "Global oil prices are predicted to remain high.",
            "user_id": 8,
            "contact_method_id": None,
        },
        attachment_inputs=[],
        analysis_result={
            "message_language_code": "en",
            "message_summary": "Oil prices are expected to stay elevated.",
            "message_text_synthesis": "",
            "moderation_status": "allowed",
            "workflow_items": [
                {
                    "item_kind": "market_topic",
                    "item_title": "Oil Market Volatility",
                    "item_summary": "Market note about global oil prices.",
                    "source_excerpt_text": "Global oil prices are predicted to remain high.",
                    "referenced_attachment_ids": [],
                    "confidence_label": "high",
                }
            ],
        },
        analysis_run_status="completed",
        now_ts_ms=1778587200000,
        connect=supplied_connect,
    )

    assert result["projection_errors"] == []
    assert result["market_topic_outputs"] == [
        {
            "market_topic_id": 55,
            "workflow_item_id": 701,
            "title": "Oil market volatility",
            "summary": "Oil prices remain elevated after geopolitical disruption.",
            "opening_ai_response_text": "Oil markets remain sensitive to supply risk.",
        }
    ]
    assert captured_usage_events[0]["connect"] is supplied_connect


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
                    "opening_ai_response_text": "EU sanctions may tighten vessel availability and raise risk premiums.",
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
            "Trade candidates:\n"
            "Offer for 200 MT urea CFR Tema for June.\n"
            "Review: https://app.dcxagent.ai/trades/objects/12\n\n"
            "#T7 Sanctions impact on fertilizer shipping to Ghana\n"
            "https://app.dcxagent.ai/me/topics/7\n\n"
            "EU sanctions may tighten vessel availability and raise risk premiums."
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


def test_policy_check_result_overrides_message_analysis_moderation() -> None:
    analysis_result = module_under_test._apply_content_policy_check_to_analysis_result(
        analysis_result={
            "moderation_status": "allowed",
            "moderation_reason_summary": "",
            "matched_prohibited_categories": [],
            "primary_workflow_kind": "trade",
            "workflow_reason_summary": "Trade found.",
            "workflow_items": [
                {
                    "item_kind": "trade",
                    "item_title": "Synthetic trade",
                    "item_summary": "Synthetic trade summary.",
                    "source_excerpt_text": "Synthetic trade.",
                    "referenced_attachment_ids": [],
                    "confidence_label": "high",
                }
            ],
        },
        policy_check_result={
            "provider_name": "google_gemini",
            "model_name": "gemini-test",
            "prompt_version": "policy-test",
            "analysis_mode": "gemini_generate_content",
            "policy_check_status": "completed",
            "moderation_status": "prohibited",
            "moderation_reason_summary": "Blocked by standalone policy check.",
            "matched_prohibited_categories": ["prohibited_fraud"],
            "should_redact_original": True,
        },
    )

    assert analysis_result["moderation_status"] == "prohibited"
    assert analysis_result["moderation_reason_summary"] == "Blocked by standalone policy check."
    assert analysis_result["matched_prohibited_categories"] == ["prohibited_fraud"]
    assert analysis_result["primary_workflow_kind"] == ""
    assert analysis_result["workflow_items"] == []
    assert analysis_result["policy_check_metadata_json"]["prompt_version"] == "policy-test"


def test_builds_topic_only_email_subject_from_topic_title(monkeypatch) -> None:
    monkeypatch.setenv("DCX_APP_BASE_URL", "https://app.dcxagent.ai")

    payload = _build_message_workflow_outcome_notification_payload(
        message_id=47,
        message_input={
            "channel_type": "email",
            "source_handle_normalized": "trader@example.com",
        },
        analysis_result={
            "moderation_status": "allowed",
        },
        analysis_run_status="completed",
        workflow_projection_result={
            "trade_outputs": [],
            "market_topic_outputs": [
                {
                    "market_topic_id": 25,
                    "title": "Maritime Security Crisis in the Strait of Hormuz",
                    "summary": "Latest maritime incident analysis.",
                    "opening_ai_response_text": "The situation in the Strait of Hormuz remains critical.",
                }
            ],
            "other_outputs": [],
            "projection_errors": [],
        },
    )

    assert payload is not None
    assert payload["subject"] == "DCX: Maritime Security Crisis in the Strait of Hormuz"


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
