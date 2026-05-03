"""
CONTEXT:
This file reads the first image attachment for one authenticated user's source contact message.
It exists so trade, topic, and trade-chat detail panels can show the originating image without
duplicating private attachment visibility joins across several read capabilities.

CONTRACT:
- preconditions:
  - authenticated_user_id identifies the current app user.
  - source_message_id is either null or one contact-message id.
- postconditions:
  - Returns None when there is no visible image attachment.
  - Returns one small attachment descriptor with the private app attachment URL path when present.
- side_effects: []
- idempotent: true
- retry_safe: true
- async: false

NARRATIVE:
WHY this exists:
  When a trade or topic was created from an image-bearing message, the detail surface should keep
  that origin visible for human review.
WHEN TO USE it:
  Use it from authenticated detail-read capabilities that already enforce ownership or participant
  visibility for the parent entity.
WHEN NOT TO USE it:
  Do not use it for public pages or unauthenticated file delivery.
WHAT CAN GO WRONG:
  The source message can be missing, hidden, or belong to another user.
WHAT COMES NEXT:
  Later detail surfaces can expose a small attachment gallery if a single preview is not enough.

TESTS:
- covered by focused detail-read smoke/build checks for now.

ERRORS:
- none; callers should treat missing image as normal absence.

CODE:
"""

from __future__ import annotations

from typing import Any


def read_authenticated_dcx_source_message_first_image_attachment(
    cursor: Any,
    authenticated_user_id: int,
    source_message_id: int | None,
) -> dict | None:
    if source_message_id is None or not isinstance(source_message_id, int) or source_message_id <= 0:
        return None

    cursor.execute(
        """
        SELECT
            attachment.id,
            attachment.file_object_id,
            attachment.sort_order,
            file_object.file_uuid,
            file_object.file_kind,
            file_object.content_type,
            file_object.file_size_bytes,
            file_object.original_filename
        FROM stephen_dcx_contact_message_attachments attachment
        INNER JOIN stephen_dcx_file_objects file_object
          ON file_object.id = attachment.file_object_id
        INNER JOIN stephen_dcx_contact_messages message
          ON message.id = attachment.message_id
        WHERE attachment.message_id = %s
          AND message.user_id = %s
          AND message.visible_to_user = TRUE
          AND file_object.file_kind = 'image'
        ORDER BY attachment.sort_order ASC, attachment.id ASC
        LIMIT 1
        """,
        (source_message_id, authenticated_user_id),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    return {
        "attachment_id": row[0],
        "file_object_id": row[1],
        "sort_order": row[2],
        "file_uuid": str(row[3]) if row[3] is not None else None,
        "file_kind": row[4],
        "content_type": row[5],
        "file_size_bytes": row[6],
        "original_filename": row[7],
        "attachment_url_path": f"/users/me/messages/{source_message_id}/attachments/{row[0]}/file",
    }
