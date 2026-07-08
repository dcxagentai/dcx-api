from admin.translations.process_due_dcx_admin_ai_translation_jobs import (
    _translate_structured_content_with_retries,
)


def test_retries_retryable_structured_translation_errors() -> None:
    call_count = 0

    def fake_translate_structured_content(**_kwargs: dict) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("API_DCX_GEMINI_ADMIN_TRANSLATION_FAILED")
        return {
            "translated_fields": {
                "email_subject": "Hola",
            },
        }

    result = _translate_structured_content_with_retries(
        translate_structured_content=fake_translate_structured_content,
        entity_kind="newsletter",
        source_language_code="en",
        target_language_code="es",
        source_fields={"email_subject": "Hello"},
    )

    assert call_count == 3
    assert result["translated_fields"]["email_subject"] == "Hola"


def test_does_not_retry_non_provider_translation_errors() -> None:
    call_count = 0

    def fake_translate_structured_content(**_kwargs: dict) -> dict:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("API_DCX_ADMIN_AI_TRANSLATION_SOURCE_NOT_FOUND")

    try:
        _translate_structured_content_with_retries(
            translate_structured_content=fake_translate_structured_content,
            entity_kind="newsletter",
            source_language_code="en",
            target_language_code="es",
            source_fields={"email_subject": "Hello"},
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_AI_TRANSLATION_SOURCE_NOT_FOUND"
    else:
        raise AssertionError("Expected non-provider error to fail without retry.")

    assert call_count == 1
