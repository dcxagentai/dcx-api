"""
CONTEXT:
This file validates one inbound message attachment, stores it in Cloudflare R2, and persists the
canonical DCX file-object and message-attachment rows.
It exists so app uploads, inbound email attachments, and inbound WhatsApp media all reuse one
private storage and metadata contract.
"""

from __future__ import annotations

import os
from pathlib import PurePosixPath
import re
from typing import Any, Callable
from uuid import UUID, uuid4

from botocore.exceptions import ClientError
import psycopg2

from files.build_dcx_r2_s3_client import build_dcx_r2_s3_client
from files.read_dcx_r2_bucket_name_for_alias import read_dcx_r2_bucket_name_for_alias
from storage.db_config import DB_CONFIG

_DCX_DEFAULT_MESSAGE_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024


def store_dcx_contact_message_attachment_file_object(
    message_id: int,
    owner_user_id: int | None,
    source_channel_type: str,
    source_provider_type: str,
    original_filename: str | None,
    file_bytes: bytes,
    content_type: str | None,
    attachment_role: str = "primary_media",
    provider_media_id: str | None = None,
    sort_order: int = 1,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    build_r2_client: Callable[[], Any] | None = None,
    file_uuid_provider: Callable[[], UUID] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - message_id identifies one existing stephen_dcx_contact_messages row.
        - file_bytes contains one non-empty attachment body.
        - The file is one supported image, audio, or document format and does not exceed the size limit.
        - The configured R2 credentials and app bucket exist.
      postconditions:
        - Uploads one private object to the DCX app R2 bucket.
        - Uses one flat opaque object key that carries no user id, message id, timestamp, or original filename.
        - Generates one route-safe file UUID for app-facing file reads.
        - Persists one stephen_dcx_file_objects row.
        - Persists one stephen_dcx_contact_message_attachments row linked to the message.
      side_effects:
        - writes one object to Cloudflare R2
        - writes to stephen_dcx_file_objects
        - writes to stephen_dcx_contact_message_attachments
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: null
      locks: []
      contention_strategy: each accepted attachment creates one fresh object key and one fresh attachment row

    NARRATIVE:
      WHY this exists:
        - DCX needs one canonical way to preserve raw inbound files before any OCR, transcription,
          or semantic routing happens.
        - R2 object keys should be storage addresses, while Postgres remains the source of truth for
          file meaning, ownership, permissions, and display names.
      WHEN TO USE it:
        - Use it after one message row already exists and you have the concrete attachment bytes.
      WHEN NOT TO USE it:
        - Do not use it for arbitrary public-site uploads or signed direct-to-R2 browser uploads.
      WHAT CAN GO WRONG:
        - The file can be empty, too large, or unsupported.
        - R2 configuration can be missing.
        - The object write can succeed while the database write fails.
      WHAT COMES NEXT:
        - Later derivation stages can read these canonical attachment rows for OCR, transcript, and
          document synthesis work.

    TESTS:
      - stores_supported_attachment_into_r2_and_database
      - stores_whatsapp_voice_note_with_parameterized_ogg_content_type
      - raises_when_attachment_exceeds_size_limit
      - raises_when_attachment_type_is_unsupported

    ERRORS:
      - API_DCX_CONTACT_MESSAGE_ATTACHMENT_INVALID:
          suggested_action: Retry with one non-empty supported file.
          common_causes:
            - empty upload
            - missing content type and filename
          recovery_steps:
            - Choose one real file and retry.
          retry_safe: true
      - API_DCX_CONTACT_MESSAGE_ATTACHMENT_TOO_LARGE:
          suggested_action: Retry with a file under 10 MB.
          common_causes:
            - attachment exceeds the configured DCX limit
          recovery_steps:
            - Compress the file or choose a smaller one.
            - Retry with a file under the limit.
          retry_safe: true
      - API_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED:
          suggested_action: Retry with one supported image, audio, PDF, DOCX, or PPTX file.
          common_causes:
            - unsupported file extension
            - unsupported content type
          recovery_steps:
            - Choose a supported format.
            - Retry the upload.
          retry_safe: true
      - API_DCX_CONTACT_MESSAGE_ATTACHMENT_STORE_FAILED:
          suggested_action: Retry after confirming storage and database health.
          common_causes:
            - R2 unavailable
            - database unavailable
          recovery_steps:
            - Confirm R2 credentials and bucket configuration.
            - Confirm database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true
          what_changed: the R2 object may already exist while file metadata rows are incomplete
          rollback_needed: inspect_before_manual_replay
          rollback_operation: inspect R2 object keys and stephen_dcx_file_objects rows for the target message id

    CODE:
    """
    if not isinstance(message_id, int) or message_id <= 0:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_INVALID")

    existing_provider_attachment = _read_existing_dcx_provider_message_attachment(
        message_id=message_id,
        provider_media_id=provider_media_id,
        connect_to_database=connect_to_database,
    )
    if existing_provider_attachment is not None:
        return existing_provider_attachment

    prepared_attachment = prepare_dcx_contact_message_attachment_file_object_storage(
        owner_user_id=owner_user_id,
        source_channel_type=source_channel_type,
        source_provider_type=source_provider_type,
        original_filename=original_filename,
        file_bytes=file_bytes,
        content_type=content_type,
        provider_media_id=provider_media_id,
        sort_order=sort_order,
        current_timestamp_ms_provider=current_timestamp_ms_provider,
        build_r2_client=build_r2_client,
        file_uuid_provider=file_uuid_provider,
    )

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                return persist_prepared_dcx_contact_message_attachment_file_object_rows(
                    cursor=cursor,
                    message_id=message_id,
                    attachment_role=attachment_role,
                    prepared_attachment=prepared_attachment,
                )
    except Exception as exc:
        delete_prepared_dcx_contact_message_attachment_file_object_from_r2(
            prepared_attachment=prepared_attachment,
            build_r2_client=build_r2_client,
        )
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_STORE_FAILED") from exc


def prepare_dcx_contact_message_attachment_file_object_storage(
    owner_user_id: int | None,
    source_channel_type: str,
    source_provider_type: str,
    original_filename: str | None,
    file_bytes: bytes,
    content_type: str | None,
    provider_media_id: str | None = None,
    sort_order: int = 1,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    build_r2_client: Callable[[], Any] | None = None,
    file_uuid_provider: Callable[[], UUID] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - file_bytes contains one non-empty attachment body.
        - The file is one supported image, audio, or document format and does not exceed the size limit.
        - The configured R2 credentials and app bucket exist.
      postconditions:
        - Uploads one private object to the DCX app R2 bucket.
        - Returns all metadata needed to persist the later file-object and attachment rows.
      side_effects:
        - writes one object to Cloudflare R2
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: null
      locks: []
      contention_strategy: callers must persist or delete the prepared object as one higher-level unit

    NARRATIVE:
      WHY this exists:
        - App uploads need to prove attachment storage can succeed before creating a visible message row.
      WHEN TO USE it:
        - Use it before inserting an app-authored message, or inside the legacy one-shot store path.
      WHEN NOT TO USE it:
        - Do not use it without either persisting the returned metadata or deleting the prepared object.
      WHAT CAN GO WRONG:
        - Validation can reject the file, or the R2 upload can fail.
      WHAT COMES NEXT:
        - The caller persists the prepared object rows after the canonical message id exists.

    TESTS:
      - stores_supported_attachment_into_r2_and_database
      - stores_whatsapp_voice_note_with_parameterized_ogg_content_type
      - raises_when_attachment_exceeds_size_limit
      - raises_when_attachment_type_is_unsupported

    ERRORS:
      - API_DCX_CONTACT_MESSAGE_ATTACHMENT_INVALID:
          suggested_action: Retry with one non-empty supported file.
          common_causes:
            - empty upload
            - missing content type and filename
          recovery_steps:
            - Choose one real file and retry.
          retry_safe: true
      - API_DCX_CONTACT_MESSAGE_ATTACHMENT_TOO_LARGE:
          suggested_action: Retry with a file under 10 MB.
          common_causes:
            - attachment exceeds the configured DCX limit
          recovery_steps:
            - Compress the file or choose a smaller one.
            - Retry with a file under the limit.
          retry_safe: true
      - API_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED:
          suggested_action: Retry with one supported image, audio, PDF, DOCX, or PPTX file.
          common_causes:
            - unsupported file extension
            - unsupported content type
          recovery_steps:
            - Choose a supported format.
            - Retry the upload.
          retry_safe: true
      - API_DCX_CONTACT_MESSAGE_ATTACHMENT_STORE_FAILED:
          suggested_action: Retry after confirming storage is healthy.
          common_causes:
            - R2 unavailable
          recovery_steps:
            - Confirm R2 credentials and bucket configuration.
            - Retry once storage is healthy.
          retry_safe: true
          what_changed: no database rows were written, but a failed cleanup may leave one orphan R2 object
          rollback_needed: inspect_before_manual_replay
          rollback_operation: inspect R2 object keys around the attempted upload time

    CODE:
    """
    if not isinstance(file_bytes, bytes) or len(file_bytes) == 0:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_INVALID")

    max_attachment_bytes = _read_dcx_message_attachment_max_bytes()
    if len(file_bytes) > max_attachment_bytes:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_TOO_LARGE")

    normalized_filename = (
        _sanitize_dcx_attachment_filename(original_filename)
        if isinstance(original_filename, str)
        else ""
    )
    normalized_content_type = (content_type or "").strip().lower()
    attachment_descriptor = _read_dcx_supported_attachment_descriptor(
        original_filename=normalized_filename,
        content_type=normalized_content_type,
    )

    now_ts_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()
    object_key = uuid4().hex
    file_uuid = (file_uuid_provider or uuid4)()
    bucket_alias = "app"
    bucket_name = read_dcx_r2_bucket_name_for_alias(bucket_alias)

    try:
        (build_r2_client or build_dcx_r2_s3_client)().put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=file_bytes,
            ContentType=attachment_descriptor["content_type"],
        )
    except ClientError as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_STORE_FAILED") from exc
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_STORE_FAILED") from exc

    return {
        "attachment_id": None,
        "file_object_id": None,
        "file_uuid": str(file_uuid),
        "file_kind": attachment_descriptor["file_kind"],
        "content_type": attachment_descriptor["content_type"],
        "original_filename": normalized_filename,
        "file_size_bytes": len(file_bytes),
        "bucket_alias": bucket_alias,
        "object_key": object_key,
        "provider_media_id": provider_media_id,
        "sort_order": sort_order,
        "stored_at_ts_ms": now_ts_ms,
        "owner_user_id": owner_user_id,
        "source_channel_type": source_channel_type,
        "source_provider_type": source_provider_type,
        "is_duplicate_provider_attachment": False,
    }


def persist_prepared_dcx_contact_message_attachment_file_object_rows(
    cursor: Any,
    message_id: int,
    attachment_role: str,
    prepared_attachment: dict,
) -> dict:
    """Minimal contract: persist one already-uploaded private file and link it to one message."""
    cursor.execute(
        """
        INSERT INTO stephen_dcx_file_objects (
            file_uuid,
            owner_user_id,
            storage_provider,
            bucket_alias,
            object_key,
            content_type,
            file_size_bytes,
            original_filename,
            file_kind,
            source_channel_type,
            source_provider_type,
            file_metadata_json,
            is_private
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
        RETURNING id
        """,
        (
            prepared_attachment["file_uuid"],
            prepared_attachment["owner_user_id"],
            "cloudflare_r2",
            prepared_attachment["bucket_alias"],
            prepared_attachment["object_key"],
            prepared_attachment["content_type"],
            prepared_attachment["file_size_bytes"],
            prepared_attachment["original_filename"],
            prepared_attachment["file_kind"],
            prepared_attachment["source_channel_type"],
            prepared_attachment["source_provider_type"],
            '{"attachment_origin":"message_ingest"}',
            True,
        ),
    )
    file_object_id = cursor.fetchone()[0]

    cursor.execute(
        """
        INSERT INTO stephen_dcx_contact_message_attachments (
            message_id,
            file_object_id,
            attachment_role,
            provider_media_id,
            sort_order
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            message_id,
            file_object_id,
            attachment_role,
            prepared_attachment.get("provider_media_id"),
            prepared_attachment["sort_order"],
        ),
    )
    attachment_id = cursor.fetchone()[0]

    return {
        **prepared_attachment,
        "attachment_id": attachment_id,
        "file_object_id": file_object_id,
    }


def delete_prepared_dcx_contact_message_attachment_file_object_from_r2(
    prepared_attachment: dict,
    build_r2_client: Callable[[], Any] | None = None,
) -> None:
    """Minimal contract: best-effort cleanup for a prepared R2 object whose DB transaction failed."""
    try:
        (build_r2_client or build_dcx_r2_s3_client)().delete_object(
            Bucket=read_dcx_r2_bucket_name_for_alias(prepared_attachment["bucket_alias"]),
            Key=prepared_attachment["object_key"],
        )
    except Exception:
        return


def _read_existing_dcx_provider_message_attachment(
    message_id: int,
    provider_media_id: str | None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    """Minimal contract: reuse one provider-media attachment already linked to this message."""
    normalized_provider_media_id = provider_media_id.strip() if isinstance(provider_media_id, str) else ""
    if normalized_provider_media_id == "":
        return None

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        attachment.id,
                        attachment.file_object_id,
                        file_object.file_uuid,
                        file_object.file_kind,
                        file_object.content_type,
                        file_object.original_filename,
                        file_object.file_size_bytes,
                        file_object.bucket_alias,
                        file_object.object_key,
                        attachment.provider_media_id,
                        attachment.sort_order
                    FROM stephen_dcx_contact_message_attachments attachment
                    INNER JOIN stephen_dcx_file_objects file_object
                      ON file_object.id = attachment.file_object_id
                    WHERE attachment.message_id = %s
                      AND attachment.provider_media_id = %s
                    ORDER BY attachment.id ASC
                    LIMIT 1
                    """,
                    (
                        message_id,
                        normalized_provider_media_id,
                    ),
                )
                existing_row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_STORE_FAILED") from exc

    if existing_row is None:
        return None

    return {
        "attachment_id": existing_row[0],
        "file_object_id": existing_row[1],
        "file_uuid": str(existing_row[2]) if existing_row[2] is not None else None,
        "file_kind": existing_row[3],
        "content_type": existing_row[4],
        "original_filename": existing_row[5],
        "file_size_bytes": existing_row[6],
        "bucket_alias": existing_row[7],
        "object_key": existing_row[8],
        "provider_media_id": existing_row[9],
        "sort_order": existing_row[10],
        "is_duplicate_provider_attachment": True,
    }


def _read_dcx_message_attachment_max_bytes() -> int:
    configured_value = os.getenv("DCX_CONTACT_MESSAGE_ATTACHMENT_MAX_BYTES", "").strip()
    if configured_value.isdigit():
        return int(configured_value)
    return _DCX_DEFAULT_MESSAGE_ATTACHMENT_MAX_BYTES


def _read_dcx_supported_attachment_descriptor(
    original_filename: str,
    content_type: str,
) -> dict:
    normalized_extension = PurePosixPath(original_filename).suffix.strip().lower()
    normalized_content_type = _read_base_dcx_attachment_content_type(content_type)

    if normalized_content_type in {"image/jpeg", "image/jpg"} or normalized_extension in {".jpg", ".jpeg"}:
        return {
            "file_kind": "image",
            "content_type": "image/jpeg",
        }
    if normalized_content_type == "image/png" or normalized_extension == ".png":
        return {
            "file_kind": "image",
            "content_type": "image/png",
        }
    if normalized_content_type == "image/webp" or normalized_extension == ".webp":
        return {
            "file_kind": "image",
            "content_type": "image/webp",
        }
    if normalized_content_type in {"audio/mpeg", "audio/mp3"} or normalized_extension == ".mp3":
        return {
            "file_kind": "audio",
            "content_type": "audio/mpeg",
        }
    if normalized_content_type in {"audio/ogg", "application/ogg"} or normalized_extension == ".ogg":
        return {
            "file_kind": "audio",
            "content_type": "audio/ogg",
        }
    if normalized_content_type in {"audio/wav", "audio/x-wav"} or normalized_extension == ".wav":
        return {
            "file_kind": "audio",
            "content_type": "audio/wav",
        }
    if normalized_content_type in {"audio/mp4", "audio/x-m4a"} or normalized_extension in {".m4a", ".mp4"}:
        return {
            "file_kind": "audio",
            "content_type": "audio/mp4",
        }
    if normalized_content_type in {"audio/aac", "audio/aacp"} or normalized_extension == ".aac":
        return {
            "file_kind": "audio",
            "content_type": "audio/aac",
        }
    if normalized_content_type == "audio/amr" or normalized_extension == ".amr":
        return {
            "file_kind": "audio",
            "content_type": "audio/amr",
        }
    if normalized_content_type == "application/pdf" or normalized_extension == ".pdf":
        return {
            "file_kind": "document",
            "content_type": "application/pdf",
        }
    if (
        normalized_content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or normalized_extension == ".docx"
    ):
        return {
            "file_kind": "document",
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
    if (
        normalized_content_type
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        or normalized_extension == ".pptx"
    ):
        return {
            "file_kind": "document",
            "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }

    if normalized_extension in {".doc", ".ppt", ".xls", ".xlsx", ".csv", ".mp4", ".mov"}:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED")

    raise RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED")


def _read_base_dcx_attachment_content_type(content_type: str) -> str:
    """Minimal contract: ignore MIME parameters such as WhatsApp voice-note codecs."""
    return content_type.strip().lower().split(";", 1)[0].strip()


def _sanitize_dcx_attachment_filename(filename: str | None) -> str:
    """Minimal contract: keep one simple path-safe filename for the stored object key."""
    if not isinstance(filename, str):
        return ""
    safe_name = PurePosixPath(filename).name.strip()
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", safe_name).strip("._")


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)
