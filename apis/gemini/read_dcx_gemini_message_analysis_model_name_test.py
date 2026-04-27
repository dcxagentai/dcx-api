import pytest

from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)


def test_returns_provider_first_gemini_message_analysis_model_env(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "gemini-3.1-flash-lite-preview")

    assert read_dcx_gemini_message_analysis_model_name() == "gemini-3.1-flash-lite-preview"


def test_raises_when_gemini_message_analysis_model_env_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_MESSAGE_ANALYSIS_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="API_DCX_GEMINI_MESSAGE_ANALYSIS_MODEL_NOT_CONFIGURED"):
        read_dcx_gemini_message_analysis_model_name()
