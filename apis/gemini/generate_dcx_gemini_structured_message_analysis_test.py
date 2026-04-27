from apis.gemini.generate_dcx_gemini_structured_message_analysis import (
    generate_dcx_gemini_structured_message_analysis,
)


def test_returns_fallback_message_analysis_when_gemini_api_key_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DCX_GEMINI_MESSAGE_ANALYSIS_MODEL", raising=False)
    monkeypatch.delenv("MODEL_DCX_TEST", raising=False)

    result = generate_dcx_gemini_structured_message_analysis(
        message_input={
            "message_id": 901,
            "channel_type": "app",
            "provider_type": "dcx_app",
            "message_format": "mixed",
            "message_subject": "",
            "raw_text_content": "See attached offer.",
        },
        file_inputs=[
            {
                "attachment_id": 71,
                "file_object_id": 81,
                "file_kind": "document",
                "content_type": "application/pdf",
                "original_filename": "offer.pdf",
                "file_size_bytes": 12,
                "file_bytes": b"pdf-bytes",
            }
        ],
    )

    assert result["analysis_mode"] == "fallback_no_model"
    assert result["message_summary"] == ""
    assert result["message_text_synthesis"] == ""
    assert result["attachments"][0]["analysis_status"] == "skipped"
    assert result["attachments"][0]["file_object_id"] == 81
    assert result["attachments"][0]["summary"] == "File stored. No model analysis is configured in this environment."
    assert result["attachments"][0]["description"] == ""


def test_returns_structured_message_analysis_from_injected_gemini_payload(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DCX_GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test")

    def _send_fake_gemini_request(request_context: dict) -> dict:
        assert "text_synthesis_requested" not in request_context["prompt_text"]
        assert "raw_text_word_count" not in request_context["prompt_text"]
        assert "Do not summarize the main text. Return an empty string for message_summary." in request_context["prompt_text"]
        assert "Do not produce a detailed synthesis of the main text" in request_context["prompt_text"]
        assert "Insert a double line break between speaker turns using actual line breaks" in request_context["prompt_text"]
        assert "Speaker A: xxx\n\n        Speaker B: xxx" in request_context["prompt_text"]
        return {
            "output_text": """
            {
              "message_language_code": "en",
              "message_summary": "",
              "message_text_synthesis": "",
              "attachments": [
                {
                  "attachment_id": 71,
                  "file_object_id": 81,
                  "filename": "voice-note.mp3",
                  "file_kind": "audio",
                  "language_code": "hi",
                  "summary": "A Hindi audio greeting.",
                  "description": "A short voice note.",
                  "transcription": "Speaker A: Namaste.Speaker B: Ji.",
                  "synthesis": "The speaker greets the recipient.",
                  "context_within_message": "This audio note is the main content of the email."
                }
              ]
            }
            """,
        }

    result = generate_dcx_gemini_structured_message_analysis(
        message_input={
            "message_id": 901,
            "channel_type": "email",
            "provider_type": "resend",
            "message_format": "mixed",
            "message_subject": "Email audio smoke test",
            "raw_text_content": "Hi, please review the attached audio.",
        },
        file_inputs=[
            {
                "attachment_id": 71,
                "file_object_id": 81,
                "file_kind": "audio",
                "content_type": "audio/mpeg",
                "original_filename": "voice-note.mp3",
                "file_size_bytes": 12,
                "file_bytes": b"audio-bytes",
            }
        ],
        send_gemini_request=_send_fake_gemini_request,
    )

    assert result["model_name"] == "gemini-test"
    assert result["message_language_code"] == "en"
    assert result["message_summary"] == ""
    assert result["attachments"][0]["language_code"] == "hi"
    assert result["attachments"][0]["summary"] == "A Hindi audio greeting."
    assert result["attachments"][0]["description"] == ""
    assert result["attachments"][0]["transcription"] == "Speaker A: Namaste.\n\nSpeaker B: Ji."


def test_includes_main_text_synthesis_instruction_only_when_python_word_count_threshold_is_met(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DCX_GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test")
    prompt_texts = []

    def _send_fake_gemini_request(request_context: dict) -> dict:
        prompt_texts.append(request_context["prompt_text"])
        return {
            "output_text": """
            {
              "message_language_code": "en",
              "message_summary": "The sender shares a long market note.",
              "message_text_synthesis": "A materially complete synthesis.",
              "attachments": []
            }
            """,
        }

    generate_dcx_gemini_structured_message_analysis(
        message_input={
            "message_id": 903,
            "channel_type": "app",
            "provider_type": "dcx_app",
            "message_format": "text",
            "message_subject": "",
            "raw_text_content": " ".join(["market"] * 500),
        },
        file_inputs=[],
        send_gemini_request=_send_fake_gemini_request,
    )

    assert "text_synthesis_requested" not in prompt_texts[0]
    assert "raw_text_word_count" not in prompt_texts[0]
    assert "Produce a detailed synthesis of the main text" in prompt_texts[0]
    assert "Do not produce a detailed synthesis of the main text" not in prompt_texts[0]
    assert "Write a 1-3 sentence summary of the main text" in prompt_texts[0]


def test_blanks_image_attachment_synthesis_from_injected_gemini_payload(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("DCX_GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test")

    result = generate_dcx_gemini_structured_message_analysis(
        message_input={
            "message_id": 902,
            "channel_type": "app",
            "provider_type": "dcx_app",
            "message_format": "image",
            "message_subject": "",
            "raw_text_content": "Please review this image.",
        },
        file_inputs=[
            {
                "attachment_id": 72,
                "file_object_id": 82,
                "file_kind": "image",
                "content_type": "image/png",
                "original_filename": "silkworms.png",
                "file_size_bytes": 12,
                "file_bytes": b"image-bytes",
            }
        ],
        send_gemini_request=lambda _request_context: {
            "output_text": """
            {
              "message_language_code": "en",
              "message_summary": "The sender asks DCX to review an image.",
              "message_text_synthesis": "",
              "attachments": [
                {
                  "attachment_id": 72,
                  "file_object_id": 82,
                  "filename": "silkworms.png",
                  "file_kind": "image",
                  "language_code": null,
                  "summary": "The image shows a sericulture workspace.",
                  "description": "A person works with trays of silkworm feed.",
                  "transcription": "",
                  "synthesis": "This image is about sericulture.",
                  "context_within_message": "The image supports the message about silk farming."
                }
              ]
            }
            """,
        },
    )

    assert result["message_summary"] == ""
    assert result["attachments"][0]["summary"] == "The image shows a sericulture workspace."
    assert result["attachments"][0]["description"] == "A person works with trays of silkworm feed."
    assert result["attachments"][0]["synthesis"] == ""
