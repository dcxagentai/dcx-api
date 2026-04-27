"""
CONTEXT:
This file reads the configured Gemini model name for the DCX message-analysis pass.
It exists so runtime code has one strict, provider-first source of truth for Gemini model
selection and fails loudly when that production-critical configuration is missing.
"""

from __future__ import annotations

import os


def read_dcx_gemini_message_analysis_model_name() -> str:
    """
    CONTRACT:
      preconditions:
        - Process environment variables must include GEMINI_MESSAGE_ANALYSIS_MODEL.
      postconditions:
        - Returns one non-empty Gemini model name string from GEMINI_MESSAGE_ANALYSIS_MODEL.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The DCX stack is normalizing provider configuration names, and Gemini message analysis
          should fail fast when its model configuration is incomplete.
      WHEN TO USE it:
        - Use it anywhere the DCX Gemini message-analysis pass needs to resolve its runtime model.
      WHEN NOT TO USE it:
        - Do not use it for OpenAI derivation, admin-configured future model catalogs, or non-message Gemini tasks.
      WHAT CAN GO WRONG:
        - GEMINI_MESSAGE_ANALYSIS_MODEL may be missing, in which case message analysis should fail
          loudly so the operator can fix live configuration quickly.
      WHAT COMES NEXT:
        - A later admin-facing configuration surface can replace env-driven selection for production tuning.

    TESTS:
      - returns_provider_first_gemini_message_analysis_model_env
      - raises_when_gemini_message_analysis_model_env_is_missing

    ERRORS:
      - API_DCX_GEMINI_MESSAGE_ANALYSIS_MODEL_NOT_CONFIGURED:
          suggested_action: Set GEMINI_MESSAGE_ANALYSIS_MODEL in the backend environment and retry.
          common_causes:
            - missing provider model env on local
            - missing provider model env on live
          recovery_steps:
            - Add GEMINI_MESSAGE_ANALYSIS_MODEL to the running environment.
            - Restart or redeploy the backend so the new env is loaded.
          retry_safe: true

    CODE:
    """
    model_name = os.getenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "").strip()
    if model_name == "":
        raise RuntimeError("API_DCX_GEMINI_MESSAGE_ANALYSIS_MODEL_NOT_CONFIGURED")
    return model_name
