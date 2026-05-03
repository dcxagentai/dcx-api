from apis.gemini.generate_dcx_gemini_market_topic_chat_response import (
    generate_dcx_gemini_market_topic_chat_response,
)
from apis.gemini.generate_dcx_gemini_structured_market_topic_seed import (
    generate_dcx_gemini_structured_market_topic_seed,
)


def test_market_topic_seed_uses_shared_system_instruction_and_omits_unused_suggestions(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test")

    def _send_fake_gemini_request(request_context: dict) -> dict:
        assert "private market-topic analysis assistant" in request_context["system_instruction"]
        assert "suggested_next_prompts" not in request_context["prompt_text"]
        assert "suggested_next_prompts" not in request_context["response_schema"]["properties"]
        assert "suggested_next_prompts" not in request_context["response_schema"]["required"]
        return {
            "output_text": """
            {
              "topic_title": "Iran Maritime Security Risk",
              "topic_summary_text": "A report suggests security risk near Gulf transit lanes.",
              "topic_scope_text": "Commercial implications for maritime security, freight, insurance, and routing.",
              "topic_tags": ["Maritime Security", "Freight"],
              "opening_ai_response_text": "If confirmed, this may affect risk premiums and route planning."
            }
            """,
        }

    result = generate_dcx_gemini_structured_market_topic_seed(
        message_input={
            "message_id": 92,
            "channel_type": "whatsapp",
            "provider_type": "twilio",
            "message_subject": "",
            "analysis_summary_text": "Screenshot of maritime alert posts.",
            "derived_text_content": "",
            "raw_text_content": "",
        },
        workflow_item={
            "item_kind": "market_topic",
            "item_title": "Iran Maritime Security Risk",
            "item_summary": "Potential security risk southwest of Iran.",
            "source_excerpt_text": "Cargo ship captain reported being attacked by small boats.",
        },
        attachment_inputs=[],
        send_gemini_request=_send_fake_gemini_request,
    )

    assert result["topic_scope_text"] == "Commercial implications for maritime security, freight, insurance, and routing."
    assert "suggested_next_prompts" not in result


def test_market_topic_chat_sends_role_based_contents_with_shared_system_instruction(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test")

    def _send_fake_gemini_request(request_context: dict) -> dict:
        assert "private market-topic analysis assistant" in request_context["system_instruction"]
        assert [content["role"] for content in request_context["contents"]] == [
            "user",
            "user",
            "model",
            "user",
        ]
        assert "conversation_so_far" not in request_context
        assert request_context["contents"][-1]["parts"][0]["text"] == "What could this do to war-risk premiums?"
        return {"output_text": "War-risk premiums may rise if the incident is confirmed."}

    result = generate_dcx_gemini_market_topic_chat_response(
        topic_context={
            "market_topic_id": 16,
            "topic_title": "Iran Maritime Security Risk",
            "topic_summary_text": "A report suggests security risk near Gulf transit lanes.",
            "topic_scope_text": "Commercial implications for maritime security, freight, insurance, and routing.",
            "topic_tags_json": ["Maritime Security", "Freight"],
        },
        prior_turns=[
            {"turn_role": "user", "turn_text": "Cargo ship captain reported being attacked."},
            {"turn_role": "assistant", "turn_text": "If confirmed, this may affect risk premiums."},
        ],
        user_turn_text="What could this do to war-risk premiums?",
        send_gemini_request=_send_fake_gemini_request,
    )

    assert result["assistant_turn_text"] == "War-risk premiums may rise if the incident is confirmed."
