from messages.derive_dcx_contact_message_text_and_language_with_llm import (
    derive_dcx_contact_message_text_and_language_with_llm,
)


def test_returns_fallback_derivation_when_openai_api_key_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = derive_dcx_contact_message_text_and_language_with_llm("Hola, quiero vender trigo.")

    assert result["derived_text_content"] == "Hola, quiero vender trigo."
    assert result["detected_language_code"] is None
    assert result["derivation_mode"] == "fallback_no_model"


def test_returns_structured_derivation_from_openai_response_payload(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DCX_OPENAI_MESSAGE_DERIVATION_MODEL", "gpt-5.2")

    def fake_send_openai_request(_: dict) -> dict:
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"derived_text_content":"Sell 5000 MT wheat FOB Rouen at 245 USD.",'
                                '"analysis_summary_text":"The message looks like a structured sell offer for wheat.",'
                                '"detected_language_code":"en"}'
                            ),
                        }
                    ],
                }
            ]
        }

    result = derive_dcx_contact_message_text_and_language_with_llm(
        "Sell 5000 MT wheat FOB Rouen at 245 USD.",
        send_openai_request=fake_send_openai_request,
    )

    assert result == {
        "derived_text_content": "Sell 5000 MT wheat FOB Rouen at 245 USD.",
        "analysis_summary_text": "The message looks like a structured sell offer for wheat.",
        "detected_language_code": "en",
        "derivation_mode": "openai_responses_api",
        "model_name": "gpt-5.2",
    }
