import json

from apis.gemini.translate_dcx_gemini_structured_admin_content import (
    translate_dcx_gemini_structured_admin_content,
)


def test_returns_translated_fields_from_structured_json_response(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test-model")
    source_fields = {
        "email_subject": "Coffee offer: 100 MT at USD 4,250",
        "email_body": "Hello {{first_name}}, see https://example.com/offer for CIF Valencia.",
    }

    def fake_send_gemini_request(_request_context: dict) -> dict:
        return {
            "output_text": json.dumps(
                {
                    "target_language_code": "es",
                    "fields": {
                        "email_subject": "Oferta de cafe: 100 MT at USD 4,250",
                        "email_body": "Hola {{first_name}}, vea https://example.com/offer para CIF Valencia.",
                    },
                }
            ),
            "usage_metadata": {"input_token_count": 10, "output_token_count": 8},
        }

    result = translate_dcx_gemini_structured_admin_content(
        entity_kind="email",
        source_language_code="en",
        target_language_code="es",
        source_fields=source_fields,
        send_gemini_request=fake_send_gemini_request,
    )

    assert result["translated_fields"]["email_body"].startswith("Hola {{first_name}}")
    assert result["provider_name"] == "google_gemini"
    assert result["model_name"] == "gemini-test-model"
    assert result["usage_metadata"] == {
        "input_token_count": 10,
        "output_token_count": 8,
        "translation_response_attempt_count": 1,
    }


def test_includes_preservation_manifest_in_prompt(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test-model")
    captured_prompt = ""

    def fake_send_gemini_request(request_context: dict) -> dict:
        nonlocal captured_prompt
        captured_prompt = request_context["prompt_text"]
        return {
            "output_text": json.dumps(
                {
                    "target_language_code": "es",
                    "fields": {
                        "email_body": "El informe de 16 paginas dice que Egipto perdio 1-0 y 3-2.",
                    },
                }
            ),
        }

    result = translate_dcx_gemini_structured_admin_content(
        entity_kind="newsletter",
        source_language_code="en",
        target_language_code="es",
        source_fields={
            "email_body": "The 16-page report says Egypt lost 1-0 and 3-2.",
        },
        send_gemini_request=fake_send_gemini_request,
    )

    assert result["prompt_version"] == "dcx_admin_structured_translation_2026_07_09_v8"
    assert "<preservation_manifest_json>" in captured_prompt
    assert '"source_token": "16"' in captured_prompt
    assert '"source_token": "1"' in captured_prompt
    assert '"source_token": "0"' in captured_prompt
    assert '"source_token": "3"' in captured_prompt
    assert '"source_token": "2"' in captured_prompt
    assert "политика-конфиденциальности-whatsapp" in captured_prompt


def test_includes_interactions_json_response_format(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test-model")
    captured_response_format = {}

    def fake_send_gemini_request(request_context: dict) -> dict:
        nonlocal captured_response_format
        captured_response_format = request_context["response_format"]
        return {
            "output_text": json.dumps(
                {
                    "target_language_code": "fr",
                    "fields": {
                        "page_slug": "politique-de-confidentialite-whatsapp",
                        "page_title": "Politique de confidentialite WhatsApp",
                    },
                }
            ),
        }

    translate_dcx_gemini_structured_admin_content(
        entity_kind="content_page",
        source_language_code="en",
        target_language_code="fr",
        source_fields={
            "page_slug": "whatsapp-privacy-policy",
            "page_title": "WhatsApp Privacy Policy",
        },
        send_gemini_request=fake_send_gemini_request,
    )

    assert captured_response_format["type"] == "text"
    assert captured_response_format["mime_type"] == "application/json"
    schema = captured_response_format["schema"]
    assert schema["properties"]["target_language_code"]["enum"] == ["fr"]
    assert schema["properties"]["fields"]["required"] == ["page_slug", "page_title"]
    assert "native script" in schema["properties"]["fields"]["properties"]["page_slug"]["description"]


def test_repairs_number_mismatch_with_validation_feedback(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test-model")
    captured_prompts = []

    def fake_send_gemini_request(request_context: dict) -> dict:
        captured_prompts.append(request_context["prompt_text"])
        if len(captured_prompts) == 1:
            return {
                "output_text": json.dumps(
                    {
                        "target_language_code": "es",
                        "fields": {
                            "email_body": "El informe dice que Egipto perdio 1-0 y 3-2.",
                        },
                    }
                ),
            }
        return {
            "output_text": json.dumps(
                {
                    "target_language_code": "es",
                    "fields": {
                        "email_body": "El informe de 16 paginas dice que Egipto perdio 1-0 y 3-2.",
                    },
                }
            ),
            "usage_metadata": {"input_token_count": 20},
        }

    result = translate_dcx_gemini_structured_admin_content(
        entity_kind="newsletter",
        source_language_code="en",
        target_language_code="es",
        source_fields={
            "email_body": "The 16-page report says Egypt lost 1-0 and 3-2.",
        },
        send_gemini_request=fake_send_gemini_request,
    )

    assert len(captured_prompts) == 2
    assert "<previous_validation_failure>" not in captured_prompts[0]
    assert "<previous_validation_failure>" in captured_prompts[1]
    assert "API_DCX_GEMINI_ADMIN_TRANSLATION_NUMBER_MISMATCH" in captured_prompts[1]
    assert "16 paginas" in result["translated_fields"]["email_body"]
    assert result["usage_metadata"]["translation_response_attempt_count"] == 2


def test_repairs_native_script_slug_mismatch_with_validation_feedback(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test-model")
    captured_prompts = []

    def fake_send_gemini_request(request_context: dict) -> dict:
        captured_prompts.append(request_context["prompt_text"])
        if len(captured_prompts) == 1:
            return {
                "output_text": json.dumps(
                    {
                        "target_language_code": "zh",
                        "fields": {
                            "page_slug": "whatsapp-yinsi-zhengce",
                            "page_title": "WhatsApp 隐私政策",
                        },
                    },
                    ensure_ascii=False,
                ),
            }
        return {
            "output_text": json.dumps(
                {
                    "target_language_code": "zh",
                    "fields": {
                        "page_slug": "whatsapp-隐私政策",
                        "page_title": "WhatsApp 隐私政策",
                    },
                },
                ensure_ascii=False,
            ),
        }

    result = translate_dcx_gemini_structured_admin_content(
        entity_kind="content_page",
        source_language_code="en",
        target_language_code="zh",
        source_fields={
            "page_slug": "whatsapp-privacy-policy",
            "page_title": "WhatsApp Privacy Policy",
        },
        send_gemini_request=fake_send_gemini_request,
    )

    assert len(captured_prompts) == 2
    assert "API_DCX_GEMINI_ADMIN_TRANSLATION_NATIVE_SCRIPT_SLUG_MISMATCH" in captured_prompts[1]
    assert result["translated_fields"]["page_slug"] == "whatsapp-隐私政策"


def test_rejects_structured_translation_with_missing_field(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test-model")

    def fake_send_gemini_request(_request_context: dict) -> dict:
        return {
            "output_text": json.dumps(
                {
                    "target_language_code": "pt",
                    "fields": {
                        "email_subject": "Oferta",
                    },
                }
            ),
        }

    try:
        translate_dcx_gemini_structured_admin_content(
            entity_kind="email",
            source_language_code="en",
            target_language_code="pt",
            source_fields={
                "email_subject": "Offer",
                "email_body": "Body",
            },
            send_gemini_request=fake_send_gemini_request,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_GEMINI_ADMIN_TRANSLATION_FIELD_MISMATCH"
    else:
        raise AssertionError("Expected field mismatch to fail.")


def test_rejects_structured_translation_with_commercial_token_drift(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test-model")

    def fake_send_gemini_request(_request_context: dict) -> dict:
        return {
            "output_text": json.dumps(
                {
                    "target_language_code": "fr",
                    "fields": {
                        "email_subject": "Prix 100 tonnes metriques en dollars",
                    },
                }
            ),
        }

    try:
        translate_dcx_gemini_structured_admin_content(
            entity_kind="email",
            source_language_code="en",
            target_language_code="fr",
            source_fields={
                "email_subject": "Price 100 MT in USD",
            },
            send_gemini_request=fake_send_gemini_request,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_GEMINI_ADMIN_TRANSLATION_COMMERCIAL_TOKEN_MISMATCH"
    else:
        raise AssertionError("Expected commercial token mismatch to fail.")


def test_allows_localized_number_formatting_and_unicode_digits(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test-model")

    def fake_send_gemini_request(_request_context: dict) -> dict:
        return {
            "output_text": json.dumps(
                {
                    "target_language_code": "ur",
                    "fields": {
                        "email_subject": "2035 target \u0665% and 3,5% for 1\u202f000 members",
                    },
                }
            ),
        }

    result = translate_dcx_gemini_structured_admin_content(
        entity_kind="newsletter",
        source_language_code="en",
        target_language_code="ur",
        source_fields={
            "email_subject": "1,000 members for 5% and 3.5% by 2035",
        },
        send_gemini_request=fake_send_gemini_request,
    )

    assert "2035" in result["translated_fields"]["email_subject"]


def test_rejects_structured_translation_with_number_drift(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-test-model")

    def fake_send_gemini_request(_request_context: dict) -> dict:
        return {
            "output_text": json.dumps(
                {
                    "target_language_code": "es",
                    "fields": {
                        "email_subject": "Objetivo del 5% para 2035",
                    },
                }
            ),
        }

    try:
        translate_dcx_gemini_structured_admin_content(
            entity_kind="newsletter",
            source_language_code="en",
            target_language_code="es",
            source_fields={
                "email_subject": "5% and 3.5% target by 2035",
            },
            send_gemini_request=fake_send_gemini_request,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error).startswith("API_DCX_GEMINI_ADMIN_TRANSLATION_NUMBER_MISMATCH:")
        assert 'source_numbers=["5", "35", "2035"]' in str(runtime_error)
    else:
        raise AssertionError("Expected number mismatch to fail.")
