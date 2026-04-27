"""
CONTEXT:
This file reads one received email's attachments from Resend and downloads the attachment bytes
needed for canonical DCX message attachment storage.
It exists so inbound email processing can preserve raw files in R2 before later OCR and document
analysis stages are introduced.
"""

from __future__ import annotations

import os
from typing import Callable

import httpx


def read_dcx_resend_received_email_attachment_inputs(
    received_email_id: str,
    list_received_email_attachments_with_provider: Callable[[str, dict], list[dict]] | None = None,
    download_attachment_bytes_with_provider: Callable[[str], bytes] | None = None,
) -> list[dict]:
    """
    CONTRACT:
      preconditions:
        - received_email_id is one non-empty Resend received-email id.
        - RESEND_API_KEY is configured in the backend environment.
      postconditions:
        - Returns zero or more standardized attachment-input dictionaries with downloaded bytes.
      side_effects:
        - performs HTTPS requests to the Resend receiving attachments API
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Email webhooks only give metadata, so DCX needs one provider adapter that can fetch and
          normalize received attachments for the shared message-attachment store.
      WHEN TO USE it:
        - Use it after a verified `email.received` webhook and after the canonical message row is
          about to ingest attachments.
      WHEN NOT TO USE it:
        - Do not use it for sent-email attachments or outbound mail status events.
      WHAT CAN GO WRONG:
        - RESEND_API_KEY can be missing.
        - The attachments list call can fail.
        - Individual attachment downloads can fail.
      WHAT COMES NEXT:
        - Later richer metadata such as content disposition or CID handling can hang off the same
          normalized attachment-input shape.

    TESTS:
      - none yet in this first multimedia pass

    ERRORS:
      - API_DCX_RESEND_RECEIVED_EMAIL_CONFIGURATION_MISSING:
          suggested_action: Configure RESEND_API_KEY before enabling inbound attachment processing.
          common_causes:
            - missing RESEND_API_KEY
          recovery_steps:
            - Add RESEND_API_KEY to the backend environment.
            - Restart the backend.
          retry_safe: true
      - API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_READ_FAILED:
          suggested_action: Retry after confirming the received email id and provider health.
          common_causes:
            - invalid received email id
            - expired download URL
            - provider outage
          recovery_steps:
            - Confirm the email id is correct.
            - Retry while the attachment download URLs are still valid.
          retry_safe: true

    CODE:
    """
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_api_key == "":
        raise RuntimeError("API_DCX_RESEND_RECEIVED_EMAIL_CONFIGURATION_MISSING")

    normalized_received_email_id = received_email_id.strip() if isinstance(received_email_id, str) else ""
    if normalized_received_email_id == "":
        raise RuntimeError("API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_READ_FAILED")

    return read_dcx_resend_received_email_attachment_fetch_result(
        received_email_id=normalized_received_email_id,
        list_received_email_attachments_with_provider=list_received_email_attachments_with_provider,
        download_attachment_bytes_with_provider=download_attachment_bytes_with_provider,
    )["attachment_inputs"]


def read_dcx_resend_received_email_attachment_fetch_result(
    received_email_id: str,
    list_received_email_attachments_with_provider: Callable[[str, dict], list[dict]] | None = None,
    download_attachment_bytes_with_provider: Callable[[str], bytes] | None = None,
) -> dict:
    """
    Minimal contract:
      - Returns both successfully downloaded attachment_inputs and any skipped attachment-read errors.
      - Attachment listing failures still raise, but one bad attachment download does not prevent the
        caller from using the remaining attachments.
    """
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_api_key == "":
        raise RuntimeError("API_DCX_RESEND_RECEIVED_EMAIL_CONFIGURATION_MISSING")

    normalized_received_email_id = received_email_id.strip() if isinstance(received_email_id, str) else ""
    if normalized_received_email_id == "":
        raise RuntimeError("API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_READ_FAILED")

    try:
        attachment_metadata_rows = (
            list_received_email_attachments_with_provider or _list_dcx_resend_received_email_attachments_with_provider
        )(
            normalized_received_email_id,
            {
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
            },
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_READ_FAILED") from exc

    attachment_inputs: list[dict] = []
    skipped_attachment_reads: list[dict] = []
    for attachment_index, attachment_metadata in enumerate(attachment_metadata_rows, start=1):
        download_url = (attachment_metadata.get("download_url") or "").strip()
        if download_url == "":
            skipped_attachment_reads.append(
                {
                    "index": attachment_index,
                    "provider_media_id": attachment_metadata.get("id"),
                    "original_filename": attachment_metadata.get("filename"),
                    "error_code": "API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_DOWNLOAD_URL_MISSING",
                }
            )
            continue
        try:
            attachment_bytes = (download_attachment_bytes_with_provider or _download_dcx_resend_attachment_bytes_with_provider)(
                download_url
            )
        except Exception:
            skipped_attachment_reads.append(
                {
                    "index": attachment_index,
                    "provider_media_id": attachment_metadata.get("id"),
                    "original_filename": attachment_metadata.get("filename"),
                    "error_code": "API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_READ_FAILED",
                }
            )
            continue

        attachment_inputs.append(
            {
                "original_filename": attachment_metadata.get("filename"),
                "content_type": attachment_metadata.get("content_type"),
                "file_bytes": attachment_bytes,
                "provider_media_id": attachment_metadata.get("id"),
            }
        )

    return {
        "attachment_inputs": attachment_inputs,
        "skipped_attachment_reads": skipped_attachment_reads,
    }


def _list_dcx_resend_received_email_attachments_with_provider(
    received_email_id: str,
    request_headers: dict,
) -> list[dict]:
    response = httpx.get(
        f"https://api.resend.com/emails/receiving/{received_email_id}/attachments",
        headers=request_headers,
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, list):
        return payload
    return []


def _download_dcx_resend_attachment_bytes_with_provider(download_url: str) -> bytes:
    response = httpx.get(
        download_url,
        timeout=60.0,
    )
    response.raise_for_status()
    return response.content
