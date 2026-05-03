from apis.gemini.build_dcx_gemini_market_topic_system_instruction import (
    build_dcx_gemini_market_topic_system_instruction,
)


def test_builds_shared_market_topic_system_instruction() -> None:
    instruction = build_dcx_gemini_market_topic_system_instruction()

    assert "DCX AI" in instruction
    assert "private market-topic analysis assistant" in instruction
    assert "ongoing monitoring" in instruction
