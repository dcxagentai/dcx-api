"""
CONTEXT:
This file calls Google Gemini to translate one private DCX trade-thread message for the
other participant in the conversation.

FLOW/SYSTEM:
- Private trader-to-trader Trade Chats.
- One participant writes in the web app.
- The backend stores the original text and, when the other participant's preferred language
  differs, stores a translated display variant for that recipient.

CONTRACT:
  preconditions:
    - message_text is non-empty trader-authored text.
    - target_language_code is a non-empty DCX language code.
    - GEMINI_API_KEY and GEMINI_MESSAGE_ANALYSIS_MODEL are configured unless send_gemini_request is injected.
  postconditions:
    - Returns translated_message_text in the requested target language.
    - Does not mutate database state.
  side_effects:
    - may call Google Gemini over HTTPS
  idempotent: true
  retry_safe: true
  async: false
  idempotency_key: trade_thread_translation:{source_language_code}:{target_language_code}:{message_text_hash}
  locks: []
  contention_strategy: caller owns persistence and can fall back to original text if translation fails

NARRATIVE:
  WHY this exists:
    - DCX's useful magic is cross-language, cross-surface trading. Private trade chats need a
      first basic translation layer so a Spanish-preferring trader and an English-preferring
      trader can read the same conversation without public leakage.
  WHEN TO USE it:
    - Use it while appending a private trade-thread message when the recipient's preferred
      language differs from the sender/app language.
  WHEN NOT TO USE it:
    - Do not use it for public forum comments, market-topic AI answers, or legal/compliance
      moderation. Those have different prompts and audit needs.
  WHAT CAN GO WRONG:
    - Provider credentials may be missing, Gemini may fail, or the output may be empty.
  WHAT COMES NEXT:
    - Later slices can add detected source language, user "happy languages", per-surface
      delivery variants, and translation retry jobs.

TESTS:
  - No dedicated unit test exists yet; smoke through private Trade Chats with two users whose
    preferred languages differ.

ERRORS:
  - API_DCX_GEMINI_TRADE_THREAD_TRANSLATION_FAILED:
      suggested_action: Save the original message and retry translation later.
      common_causes:
        - missing GEMINI_API_KEY
        - missing GEMINI_MESSAGE_ANALYSIS_MODEL
        - transient provider failure
        - empty model response
      recovery_steps:
        - Verify Gemini credentials and provider health.
        - Re-run translation for the affected message if needed.
      retry_safe: true

CODE:
"""

from __future__ import annotations

import hashlib
import os
from typing import Callable

from apis.gemini.read_dcx_gemini_message_analysis_model_name import (
    read_dcx_gemini_message_analysis_model_name,
)

PROMPT_VERSION_DCX_TRADE_THREAD_TRANSLATION = "dcx_trade_thread_translation_2026_05_01_v1"


def translate_dcx_gemini_trade_thread_message(
    message_text: str,
    source_language_code: str,
    target_language_code: str,
    send_gemini_request: Callable[[dict], dict] | None = None,
) -> dict:
    normalized_message_text = message_text.strip() if isinstance(message_text, str) else ""
    normalized_source_language_code = (
        source_language_code.strip().lower() if isinstance(source_language_code, str) else "auto"
    ) or "auto"
    normalized_target_language_code = (
        target_language_code.strip().lower() if isinstance(target_language_code, str) else ""
    )
    if normalized_message_text == "" or normalized_target_language_code == "":
        raise RuntimeError("API_DCX_GEMINI_TRADE_THREAD_TRANSLATION_FAILED")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = read_dcx_gemini_message_analysis_model_name()
    if api_key == "" and send_gemini_request is None:
        raise RuntimeError("API_DCX_GEMINI_TRADE_THREAD_TRANSLATION_FAILED")

    prompt_text = _build_trade_thread_translation_prompt(
        message_text=normalized_message_text,
        source_language_code=normalized_source_language_code,
        target_language_code=normalized_target_language_code,
    )
    request_context = {
        "api_key": api_key,
        "model_name": model_name,
        "prompt_text": prompt_text,
    }

    try:
        response_payload = (send_gemini_request or _send_gemini_generate_content_request)(request_context)
        translated_message_text = str(response_payload.get("output_text", "")).strip()
    except Exception as exc:
        raise RuntimeError("API_DCX_GEMINI_TRADE_THREAD_TRANSLATION_FAILED") from exc

    if translated_message_text == "":
        raise RuntimeError("API_DCX_GEMINI_TRADE_THREAD_TRANSLATION_FAILED")

    return {
        "translated_message_text": translated_message_text,
        "provider_name": "google_gemini",
        "model_name": model_name,
        "prompt_version": PROMPT_VERSION_DCX_TRADE_THREAD_TRANSLATION,
        "prompt_fingerprint": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
    }


def _send_gemini_generate_content_request(request_context: dict) -> dict:
    from google import genai

    client = genai.Client(api_key=request_context["api_key"])
    response = client.models.generate_content(
        model=request_context["model_name"],
        contents=[request_context["prompt_text"]],
    )
    return {"output_text": (response.text or "").strip()}


def _build_trade_thread_translation_prompt(
    message_text: str,
    source_language_code: str,
    target_language_code: str,
) -> str:
    return f"""
<dcx_task>
Translate one private trader-to-trader trade chat message.
Return only the translated message text. Do not return JSON.
</dcx_task>

<translation_rules>
- Translate into target_language_code={target_language_code}.
- Preserve the commercial meaning, quantities, units, currencies, dates, locations, names, and trade terms.
- Preserve line breaks when useful.
- Do not add advice, explanations, warnings, or commentary.
- If source_language_code={source_language_code} is wrong, infer the real source language from the text and still translate to the target language.
- If the text is already in the target language, return it unchanged.
</translation_rules>

<message_text>
{message_text}
</message_text>
""".strip()
