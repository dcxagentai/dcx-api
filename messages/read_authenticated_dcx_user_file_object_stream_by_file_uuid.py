"""
CONTEXT:
This file reads one authenticated DCX user's private file object by its route-safe file UUID.
It exists so app-facing file URLs can be flat and opaque without exposing message ids,
attachment ids, database ids, or R2 object keys.
"""

from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from botocore.exceptions import ClientError
import psycopg2

from files.build_dcx_r2_s3_client import build_dcx_r2_s3_client
from files.read_dcx_r2_bucket_name_for_alias import read_dcx_r2_bucket_name_for_alias
from storage.db_config import DB_CONFIG


def read_authenticated_dcx_user_file_object_stream_by_file_uuid(
    authenticated_user_id: int,
    file_uuid: str,
    connect_to_database: Callable[..., Any] | None = None,
    build_r2_client: Callable[[], Any] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one current DCX user.
        - file_uuid is one canonical UUID string.
      postconditions:
        - Returns one file payload with bytes and metadata when the user owns the file object.
        - Returns null when the UUID is invalid, missing, or not visible to that user.
      side_effects:
        - performs one R2 read when the file exists
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Browser-visible file URLs should be flat and route-safe while keeping all storage meaning
          in Postgres and all bytes in private R2.
      WHEN TO USE it:
        - Use it from authenticated app routes serving private user files.
      WHEN NOT TO USE it:
        - Do not use it for public files, admin cross-user inspection, or unsigned direct R2 access.
      WHAT CAN GO WRONG:
        - The UUID can be invalid.
        - The file can belong to another user.
        - The backing R2 object can be missing.
      WHAT COMES NEXT:
        - Future explicit sharing can extend the authorization query to include file access grants.

    TESTS:
      - returns_file_stream_when_file_uuid_belongs_to_user
      - returns_none_when_file_uuid_is_invalid
      - returns_none_when_file_uuid_is_missing

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_FILE_OBJECT_READ_FAILED:
          suggested_action: Retry after confirming the file exists and storage is healthy.
          common_causes:
            - missing R2 object
            - database unavailable
            - wrong file UUID
          recovery_steps:
            - Confirm the file UUID is correct.
            - Confirm R2 and database health.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    try:
        normalized_file_uuid = str(UUID(str(file_uuid).strip()))
    except (TypeError, ValueError, AttributeError):
        return None

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        file_object.bucket_alias,
                        file_object.object_key,
                        file_object.content_type,
                        file_object.original_filename,
                        file_object.file_kind,
                        message.analysis_metadata_json
                    FROM stephen_dcx_file_objects file_object
                    LEFT JOIN stephen_dcx_contact_message_attachments attachment
                      ON attachment.file_object_id = file_object.id
                    LEFT JOIN stephen_dcx_contact_messages message
                      ON message.id = attachment.message_id
                    WHERE file_object.owner_user_id = %s
                      AND file_object.file_uuid = %s
                      AND file_object.is_private = TRUE
                    LIMIT 1
                    """,
                    (
                        authenticated_user_id,
                        normalized_file_uuid,
                    ),
                )
                file_object_row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_FILE_OBJECT_READ_FAILED") from exc

    if file_object_row is None:
        return None

    if _read_dcx_message_is_prohibited_from_analysis_metadata_json(file_object_row[5]):
        return None

    try:
        r2_object_response = (build_r2_client or build_dcx_r2_s3_client)().get_object(
            Bucket=read_dcx_r2_bucket_name_for_alias(file_object_row[0]),
            Key=file_object_row[1],
        )
    except ClientError as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_FILE_OBJECT_READ_FAILED") from exc
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_FILE_OBJECT_READ_FAILED") from exc

    return {
        "content_bytes": r2_object_response["Body"].read(),
        "content_type": file_object_row[2] or "application/octet-stream",
        "original_filename": file_object_row[3] or "attachment",
        "file_kind": file_object_row[4] or "other",
    }


def _read_dcx_message_is_prohibited_from_analysis_metadata_json(analysis_metadata_json: Any) -> bool:
    if not isinstance(analysis_metadata_json, dict):
        return False
    return str(analysis_metadata_json.get("moderation_status") or "").strip().lower() == "prohibited"
