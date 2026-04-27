"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for reading one private message attachment.
It exists so the Messages surface can preview or download files from app, email, and WhatsApp
without exposing direct R2 URLs.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from messages.read_authenticated_dcx_user_contact_message_attachment_stream import (
    read_authenticated_dcx_user_contact_message_attachment_stream,
)

dcx_api_routes_users_me_message_attachment_file_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_message_attachment_file_router.get(
    "/me/messages/{message_id}/attachments/{attachment_id}/file",
    response_model=None,
)
def get_authenticated_dcx_user_message_attachment_file(
    request: Request,
    message_id: int,
    attachment_id: int,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session is active.
        - message_id and attachment_id identify one visible attachment for that user.
      postconditions:
        - Returns the attachment bytes as a streamed HTTP response when the file is visible.
        - Returns a canonical JSON error wrapper when the file is missing or unreadable.
      side_effects:
        - performs one backend storage read
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The app needs a private file-read route to preview and download inbound attachments.
        - Browser media elements and open-in-new-tab downloads do not reliably include an Origin
          header, so this read-only route relies on session authentication plus ownership checks.
      WHEN TO USE it:
        - Use it from the authenticated app Messages surface.
      WHEN NOT TO USE it:
        - Do not use it for public-site file delivery or admin cross-user inspection.
      WHAT CAN GO WRONG:
        - The session can be missing.
        - The attachment can belong to another user.
        - The backing object can be missing from storage.
      WHAT COMES NEXT:
        - Future signed-delivery or caching layers can sit behind this same narrow boundary.

    TESTS:
      - covered indirectly by the attachment stream capability tests and app route tests

    ERRORS:
      - API_USERS_ME_MESSAGE_ATTACHMENT_NOT_FOUND:
          suggested_action: Refresh the inbox and retry with one current attachment row.
          common_causes:
            - wrong message id
            - wrong attachment id
            - attachment belongs to another user
          recovery_steps:
            - Refresh the Messages view.
            - Retry with one visible attachment.
          retry_safe: true
      - API_USERS_ME_MESSAGE_ATTACHMENT_READ_FAILED:
          suggested_action: Retry after confirming backend storage is healthy.
          common_causes:
            - missing R2 object
            - storage outage
          recovery_steps:
            - Confirm R2 health and attachment presence.
            - Retry once storage is healthy.
          retry_safe: true

    CODE:
    """
    authenticated_user_id, _identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        attachment_stream = read_authenticated_dcx_user_contact_message_attachment_stream(
            authenticated_user_id=authenticated_user_id,
            message_id=message_id,
            attachment_id=attachment_id,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MESSAGE_ATTACHMENT_READ_FAILED",
                    "message": "We could not load that attachment right now.",
                    "suggested_action": "Retry in a moment after the backend storage layer is healthy.",
                },
            },
        )

    if attachment_stream is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MESSAGE_ATTACHMENT_NOT_FOUND",
                    "message": "That attachment does not exist for this account.",
                    "suggested_action": "Refresh the inbox and retry with one visible attachment.",
                },
            },
        )

    return Response(
        content=attachment_stream["content_bytes"],
        media_type=attachment_stream["content_type"],
        headers={
            "Content-Disposition": f'inline; filename="{attachment_stream["original_filename"]}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
