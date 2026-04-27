import os

from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)


def test_prefers_provider_first_gemini_message_analysis_model_env(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-3.1-flash-lite-preview")
    monkeypatch.setenv("DCX_GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-legacy")
    monkeypatch.setenv("MODEL_DCX_TEST", "gemini-test")

    assert read_dcx_gemini_message_analysis_model_name() == "gemini-3.1-flash-lite-preview"


def test_falls_back_to_legacy_dcx_prefixed_model_env(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MESSAGE_ANALYSIS_MODEL", raising=False)
    monkeypatch.setenv("DCX_GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-legacy")
    monkeypatch.setenv("MODEL_DCX_TEST", "gemini-test")

    assert read_dcx_gemini_message_analysis_model_name() == "gemini-legacy"


def test_falls_back_to_local_default_when_no_env_is_present(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MESSAGE_ANALYSIS_MODEL", raising=False)
    monkeypatch.delenv("DCX_GEMINI_MESSAGE_ANALYSIS_MODEL", raising=False)
    monkeypatch.delenv("MODEL_DCX_TEST", raising=False)

    assert read_dcx_gemini_message_analysis_model_name() == "gemini-2.5-flash"
