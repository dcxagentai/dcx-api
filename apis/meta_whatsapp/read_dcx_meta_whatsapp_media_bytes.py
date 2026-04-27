"""
CONTEXT:
This file reads one inbound Meta WhatsApp media object and returns the raw bytes needed for DCX
message attachment storage.
It exists so inbound WhatsApp image, audio, and document messages can preserve their raw media in
R2 before transcription, OCR, and document understanding are layered on later.
"""

from __future__ import annotations

import os
from typing import Callable

import httpx


def read_dcx_meta_whatsapp_media_bytes(
    media_id: str,
    fetch_media_metadata_with_provider: Callable[[str, str, str], dict] | None = None,
    fetch_media_bytes_with_provider: Callable[[str, str], bytes] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - media_id is one non-empty Meta WhatsApp media id.
        - META_WHATSAPP_TOKEN is configured in the backend environment.
        - META_API_VERSION is configured or defaults to one valid Graph API version.
      postconditions:
        - Returns one standardized media payload with bytes and metadata.
      side_effects:
        - performs HTTPS requests to the Meta Graph API
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The webhook payload only carries media ids, so DCX needs one provider adapter that can
          fetch the actual file bytes for shared attachment storage.
      WHEN TO USE it:
        - Use it while processing one verified inbound WhatsApp webhook envelope that references
          image, audio, or document media.
      WHEN NOT TO USE it:
        - Do not use it for plain text WhatsApp messages or the GET webhook handshake.
      WHAT CAN GO WRONG:
        - The bearer token can be missing.
        - The media id can be invalid or expired.
        - The provider download can fail.
      WHAT COMES NEXT:
        - Later richer media metadata or resumable large-download flows can layer onto the same
          standard return shape.

    TESTS:
      - none yet in this first multimedia pass

    ERRORS:
      - API_DCX_META_WHATSAPP_MEDIA_CONFIGURATION_MISSING:
          suggested_action: Configure the Meta WhatsApp token before enabling media ingest.
          common_causes:
            - missing META_WHATSAPP_TOKEN
          recovery_steps:
            - Add META_WHATSAPP_TOKEN to the backend environment.
            - Restart the backend.
          retry_safe: true
      - API_DCX_META_WHATSAPP_MEDIA_READ_FAILED:
          suggested_action: Retry after confirming the media id is valid and the provider is healthy.
          common_causes:
            - invalid media id
            - expired media URL
            - provider outage
          recovery_steps:
            - Confirm the webhook payload contains a valid media id.
            - Retry once the provider is healthy.
          retry_safe: true

    CODE:
    """
    normalized_media_id = media_id.strip() if isinstance(media_id, str) else ""
    if normalized_media_id == "":
        raise RuntimeError("API_DCX_META_WHATSAPP_MEDIA_READ_FAILED")

    bearer_token = os.getenv("META_WHATSAPP_TOKEN", "").strip()
    if bearer_token == "":
        raise RuntimeError("API_DCX_META_WHATSAPP_MEDIA_CONFIGURATION_MISSING")

    api_version = os.getenv("META_API_VERSION", "").strip() or "v23.0"

    try:
        media_metadata = (fetch_media_metadata_with_provider or _fetch_dcx_meta_whatsapp_media_metadata_with_provider)(
            normalized_media_id,
            api_version,
            bearer_token,
        )
        media_url = (media_metadata.get("url") or "").strip()
        if media_url == "":
            raise RuntimeError("API_DCX_META_WHATSAPP_MEDIA_READ_FAILED")
        media_bytes = (fetch_media_bytes_with_provider or _fetch_dcx_meta_whatsapp_media_bytes_with_provider)(
            media_url,
            bearer_token,
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_META_WHATSAPP_MEDIA_READ_FAILED") from exc

    return {
        "media_id": normalized_media_id,
        "content_type": (media_metadata.get("mime_type") or "").strip().lower() or None,
        "file_bytes": media_bytes,
        "sha256": media_metadata.get("sha256"),
        "file_size_bytes": media_metadata.get("file_size"),
    }


def _fetch_dcx_meta_whatsapp_media_metadata_with_provider(
    media_id: str,
    api_version: str,
    bearer_token: str,
) -> dict:
    response = httpx.get(
        f"https://graph.facebook.com/{api_version}/{media_id}",
        headers={
            "Authorization": f"Bearer {bearer_token}",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def _fetch_dcx_meta_whatsapp_media_bytes_with_provider(media_url: str, bearer_token: str) -> bytes:
    response = httpx.get(
        media_url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.content
