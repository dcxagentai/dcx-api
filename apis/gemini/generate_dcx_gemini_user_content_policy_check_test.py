from apis.gemini.generate_dcx_gemini_user_content_policy_check import (
    generate_dcx_gemini_user_content_policy_check,
)


def test_returns_not_reviewed_policy_check_when_gemini_api_key_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test")

    result = generate_dcx_gemini_user_content_policy_check(
        content_input={
            "content_id": 901,
            "content_kind": "ai_chat_turn",
            "surface": "app",
            "channel_type": "app",
            "provider_type": "dcx_app",
            "message_format": "text",
            "message_subject": "",
            "raw_text_content": "What are the main risks in cocoa logistics this week?",
        },
        file_inputs=[],
    )

    assert result["policy_check_status"] == "skipped"
    assert result["analysis_mode"] == "fallback_no_model"
    assert result["moderation_status"] == "not_reviewed"
    assert result["matched_prohibited_categories"] == []
    assert result["should_redact_original"] is False


def test_returns_normalized_prohibited_policy_check_from_injected_gemini_payload(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test")

    prompt_texts = []

    def _send_fake_gemini_request(request_context: dict) -> dict:
        prompt_texts.append(request_context["prompt_text"])
        assert "Judge the user's likely intent from context" in request_context["prompt_text"]
        assert "Attempts to evade sanctions" in request_context["prompt_text"]
        assert "prohibited_sanctions" in request_context["prompt_text"]
        return {
            "output_text": """
            {
              "moderation_status": "prohibited",
              "matched_prohibited_categories": [
                "prohibited_sanctions",
                "prohibited_fraud",
                "prohibited_sanctions",
                "unknown_code"
              ],
              "moderation_reason_summary": "The user asks for sanctions evasion and document falsification help.",
              "user_facing_message": "This input was blocked by DCX policy.",
              "should_redact_original": false
            }
            """,
            "usage_metadata": {"total_token_count": 77},
        }

    result = generate_dcx_gemini_user_content_policy_check(
        content_input={
            "content_id": 902,
            "content_kind": "message",
            "surface": "app",
            "channel_type": "app",
            "provider_type": "dcx_app",
            "message_format": "text",
            "message_subject": "",
            "raw_text_content": "Synthetic prohibited test message.",
        },
        file_inputs=[
            {
                "attachment_id": 71,
                "file_object_id": 81,
                "file_kind": "document",
                "content_type": "application/pdf",
                "original_filename": "paper.pdf",
                "file_size_bytes": 12,
                "file_bytes": b"pdf-bytes",
            }
        ],
        send_gemini_request=_send_fake_gemini_request,
    )

    assert prompt_texts
    assert result["policy_check_status"] == "completed"
    assert result["model_name"] == "gemini-test"
    assert result["moderation_status"] == "prohibited"
    assert result["matched_prohibited_categories"] == [
        "prohibited_sanctions",
        "prohibited_fraud",
    ]
    assert result["moderation_reason_summary"] == "The user asks for sanctions evasion and document falsification help."
    assert result["should_redact_original"] is True
    assert result["usage_metadata"] == {"total_token_count": 77}


def test_clears_reason_fields_for_allowed_policy_check(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test")

    result = generate_dcx_gemini_user_content_policy_check(
        content_input={
            "content_id": 903,
            "content_kind": "message",
            "surface": "email",
            "channel_type": "email",
            "provider_type": "resend",
            "message_format": "text",
            "message_subject": "Sanctions impact",
            "raw_text_content": "How are sanctions changing freight availability for diesel traders?",
        },
        file_inputs=[],
        send_gemini_request=lambda _request_context: {
            "output_text": """
            {
              "moderation_status": "allowed",
              "matched_prohibited_categories": ["prohibited_sanctions"],
              "moderation_reason_summary": "Allowed market context.",
              "user_facing_message": "Should be cleared.",
              "should_redact_original": true
            }
            """
        },
    )

    assert result["moderation_status"] == "allowed"
    assert result["matched_prohibited_categories"] == []
    assert result["moderation_reason_summary"] == ""
    assert result["user_facing_message"] == ""
    assert result["should_redact_original"] is False
