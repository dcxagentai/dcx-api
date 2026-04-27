"""
CONTEXT:
This file reads one authenticated DCX user's message attachment bytes from Cloudflare R2.
It exists so the app can render or download private inbound attachments through the backend rather
than exposing direct R2 access.
"""

from __future__ import annotations

from typing import Any, Callable

from botocore.exceptions import ClientError
import psycopg2

from files.build_dcx_r2_s3_client import build_dcx_r2_s3_client
from files.read_dcx_r2_bucket_name_for_alias import read_dcx_r2_bucket_name_for_alias
from storage.db_config import DB_CONFIG


def read_authenticated_dcx_user_contact_message_attachment_stream(
    authenticated_user_id: int,
    message_id: int,
    attachment_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    build_r2_client: Callable[[], Any] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one current DCX user.
        - message_id identifies one visible message row owned by that user.
        - attachment_id identifies one attachment row linked to that message.
      postconditions:
        - Returns one attachment payload with bytes and metadata when the user can access it.
        - Returns null when the attachment is not visible to that user.
      side_effects:
        - performs one R2 read when the attachment exists
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The Messages app surface needs one private file-read boundary for previews and download
          actions across app, email, and WhatsApp attachments.
      WHEN TO USE it:
        - Use it from an authenticated backend route serving one message attachment.
      WHEN NOT TO USE it:
        - Do not use it for public-site files or admin cross-user inspection.
      WHAT CAN GO WRONG:
        - The attachment may not belong to the current user.
        - The backing R2 object may be missing.
      WHAT COMES NEXT:
        - Future authorization-aware signed delivery can evolve behind the same capability.

    TESTS:
      - returns_attachment_stream_when_attachment_belongs_to_user
      - returns_none_when_attachment_is_missing

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_MESSAGE_ATTACHMENT_READ_FAILED:
          suggested_action: Retry after confirming the attachment still exists and storage is healthy.
          common_causes:
            - missing R2 object
            - database unavailable
            - wrong attachment id
          recovery_steps:
            - Confirm the message and attachment ids are correct.
            - Confirm R2 and database health.
            - Retry the request.
          retry_safe: true

    CODE:
    """
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
                        file_object.file_kind
                    FROM stephen_dcx_contact_message_attachments attachment
                    INNER JOIN stephen_dcx_contact_messages message
                      ON message.id = attachment.message_id
                    INNER JOIN stephen_dcx_file_objects file_object
                      ON file_object.id = attachment.file_object_id
                    WHERE message.user_id = %s
                      AND message.id = %s
                      AND attachment.id = %s
                      AND message.visible_to_user = TRUE
                    LIMIT 1
                    """,
                    (
                        authenticated_user_id,
                        message_id,
                        attachment_id,
                    ),
                )
                attachment_row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGE_ATTACHMENT_READ_FAILED") from exc

    if attachment_row is None:
        return None

    try:
        r2_object_response = (build_r2_client or build_dcx_r2_s3_client)().get_object(
            Bucket=read_dcx_r2_bucket_name_for_alias(attachment_row[0]),
            Key=attachment_row[1],
        )
    except ClientError as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGE_ATTACHMENT_READ_FAILED") from exc
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MESSAGE_ATTACHMENT_READ_FAILED") from exc

    return {
        "content_bytes": r2_object_response["Body"].read(),
        "content_type": attachment_row[2] or "application/octet-stream",
        "original_filename": attachment_row[3] or "attachment",
        "file_kind": attachment_row[4] or "other",
    }
