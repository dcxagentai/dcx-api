"""
CONTEXT:
This file reads the configured Gemini model name for the DCX message-analysis pass.
It exists so runtime code can move toward clearer provider-first environment variable naming
without breaking existing environments that still use the older DCX-prefixed key.
"""

from __future__ import annotations

import os


def read_dcx_gemini_message_analysis_model_name() -> str:
    """
    CONTRACT:
      preconditions:
        - Process environment variables may or may not include Gemini model configuration.
      postconditions:
        - Returns one non-empty Gemini model name string.
        - Prefers the provider-first GEMINI_MESSAGE_ANALYSIS_MODEL key.
        - Falls back to the older DCX_GEMINI_MESSAGE_ANALYSIS_MODEL key for compatibility.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The DCX stack is starting to normalize provider configuration names, and Gemini model
          selection is the first live path we want to clean up without breaking current deploys.
      WHEN TO USE it:
        - Use it anywhere the DCX Gemini message-analysis pass needs to resolve its runtime model.
      WHEN NOT TO USE it:
        - Do not use it for OpenAI derivation, admin-configured future model catalogs, or non-message Gemini tasks.
      WHAT CAN GO WRONG:
        - Neither environment variable may be set, in which case the local default must carry the flow.
      WHAT COMES NEXT:
        - A later admin-facing configuration surface can replace env-driven selection for production tuning.

    TESTS:
      - prefers_provider_first_gemini_message_analysis_model_env
      - falls_back_to_legacy_dcx_prefixed_model_env
      - falls_back_to_local_default_when_no_env_is_present

    ERRORS:
      - none:
          suggested_action: Not applicable.
          common_causes: []
          recovery_steps: []
          retry_safe: true

    CODE:
    """
    return (
        os.getenv("GEMINI_MESSAGE_ANALYSIS_MODEL", "").strip()
        or os.getenv("DCX_GEMINI_MESSAGE_ANALYSIS_MODEL", "").strip()
        or os.getenv("MODEL_DCX_TEST", "").strip()
        or "gemini-2.5-flash"
    )
