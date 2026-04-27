"""
CONTEXT:
This file builds the canonical Cloudflare R2 S3-compatible client for DCX backend capabilities.
It exists so message attachments and future private-file flows reuse one credential and endpoint
resolution path instead of duplicating boto3 client construction in every boundary.
"""

from __future__ import annotations

import os

import boto3
from botocore.config import Config
from botocore.client import BaseClient


def build_dcx_r2_s3_client() -> BaseClient:
    """
    CONTRACT:
      preconditions:
        - DCX_R2_ACCESS_KEY_ID and DCX_R2_SECRET_ACCESS_KEY are configured.
        - Either DCX_R2_S3_ENDPOINT_URL or DCX_R2_ACCOUNT_ID is configured.
      postconditions:
        - Returns one boto3 S3-compatible client for Cloudflare R2.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Message attachments, future document delivery, and smoke-test routes all need one stable
          R2 client factory.
      WHEN TO USE it:
        - Use it whenever a backend capability needs to read or write a DCX object in R2.
      WHEN NOT TO USE it:
        - Do not use it for public third-party object stores that are not part of DCX R2.
      WHAT CAN GO WRONG:
        - Credentials can be missing.
        - The endpoint can be missing or malformed.
      WHAT COMES NEXT:
        - Future signed-download or presigned-upload flows can build on the same client factory.

    TESTS:
      - covered indirectly by the existing R2 hello-world route tests

    ERRORS:
      - API_DCX_R2_CONFIGURATION_MISSING:
          suggested_action: Configure the required R2 environment variables and retry.
          common_causes:
            - missing DCX_R2_ACCESS_KEY_ID
            - missing DCX_R2_SECRET_ACCESS_KEY
            - missing DCX_R2_ACCOUNT_ID
          recovery_steps:
            - Add the required R2 credentials to the backend environment.
            - Restart the backend.
          retry_safe: true

    CODE:
    """
    access_key_id = os.getenv("DCX_R2_ACCESS_KEY_ID", "").strip()
    secret_access_key = os.getenv("DCX_R2_SECRET_ACCESS_KEY", "").strip()
    if access_key_id == "" or secret_access_key == "":
        raise RuntimeError("API_DCX_R2_CONFIGURATION_MISSING")

    return boto3.client(
        "s3",
        endpoint_url=_read_dcx_r2_s3_endpoint_url(),
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
        config=Config(
            connect_timeout=_read_dcx_r2_timeout_seconds("DCX_R2_CONNECT_TIMEOUT_SECONDS", 5),
            read_timeout=_read_dcx_r2_timeout_seconds("DCX_R2_READ_TIMEOUT_SECONDS", 15),
            retries={
                "max_attempts": _read_dcx_r2_retry_attempts(),
                "mode": "standard",
            },
            s3={
                "addressing_style": "path",
            },
        ),
    )


def _read_dcx_r2_s3_endpoint_url() -> str:
    """Minimal contract: return the configured R2 endpoint or derive it from the Cloudflare account id."""
    configured_endpoint_url = os.getenv("DCX_R2_S3_ENDPOINT_URL", "").strip()
    if configured_endpoint_url != "":
        return configured_endpoint_url

    account_id = os.getenv("DCX_R2_ACCOUNT_ID", "").strip()
    if account_id == "":
        raise RuntimeError("API_DCX_R2_CONFIGURATION_MISSING")

    return f"https://{account_id}.r2.cloudflarestorage.com"


def _read_dcx_r2_timeout_seconds(env_var_name: str, default_seconds: int) -> int:
    configured_value = os.getenv(env_var_name, "").strip()
    if configured_value == "":
        return default_seconds
    try:
        parsed_value = int(configured_value)
    except ValueError:
        return default_seconds
    return max(1, min(parsed_value, 60))


def _read_dcx_r2_retry_attempts() -> int:
    configured_value = os.getenv("DCX_R2_MAX_ATTEMPTS", "").strip()
    if configured_value == "":
        return 2
    try:
        parsed_value = int(configured_value)
    except ValueError:
        return 2
    return max(1, min(parsed_value, 5))
