"""
CONTEXT:
This file resolves one canonical DCX R2 bucket alias into its configured concrete bucket name.
It exists so message attachments and other file capabilities can refer to stable semantic bucket
aliases instead of hardcoding environment variable names in every file capability.
"""

from __future__ import annotations

import os


def read_dcx_r2_bucket_name_for_alias(bucket_alias: str) -> str:
    """
    CONTRACT:
      preconditions:
        - bucket_alias is one supported DCX alias.
        - The matching R2 bucket environment variable is configured.
      postconditions:
        - Returns the concrete bucket name for the requested alias.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Backend capabilities should talk about semantic bucket roles such as `app` rather than
          knowing which env var holds the actual bucket name.
      WHEN TO USE it:
        - Use it before reading from or writing to one DCX R2 bucket.
      WHEN NOT TO USE it:
        - Do not use it for arbitrary non-DCX bucket names supplied by clients.
      WHAT CAN GO WRONG:
        - The alias can be unsupported.
        - The configured bucket env var can be missing.
      WHAT COMES NEXT:
        - Additional bucket roles can be added here without changing every capability.

    TESTS:
      - covered indirectly by the existing R2 hello-world route tests

    ERRORS:
      - API_DCX_R2_BUCKET_ALIAS_INVALID:
          suggested_action: Retry with one supported DCX bucket alias.
          common_causes:
            - unsupported alias
          recovery_steps:
            - Use app or public.
          retry_safe: true
      - API_DCX_R2_CONFIGURATION_MISSING:
          suggested_action: Configure the required bucket environment variable and retry.
          common_causes:
            - missing DCX_R2_APP_BUCKET_NAME
            - missing DCX_R2_PUBLIC_BUCKET_NAME
          recovery_steps:
            - Add the bucket name to the backend environment.
            - Restart the backend.
          retry_safe: true

    CODE:
    """
    normalized_bucket_alias = bucket_alias.strip().lower()
    if normalized_bucket_alias not in {"app", "public"}:
        raise RuntimeError("API_DCX_R2_BUCKET_ALIAS_INVALID")

    bucket_env_var_name = (
        "DCX_R2_APP_BUCKET_NAME"
        if normalized_bucket_alias == "app"
        else "DCX_R2_PUBLIC_BUCKET_NAME"
    )
    bucket_name = os.getenv(bucket_env_var_name, "").strip()
    if bucket_name == "":
        raise RuntimeError("API_DCX_R2_CONFIGURATION_MISSING")

    return bucket_name
