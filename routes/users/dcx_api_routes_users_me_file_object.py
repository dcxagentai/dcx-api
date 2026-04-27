"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for reading one private user file by file UUID.
It exists so app-visible file URLs are flat, opaque, and decoupled from message ids, attachment ids,
database primary keys, and R2 object keys.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from messages.read_authenticated_dcx_user_file_object_stream_by_file_uuid import (
    read_authenticated_dcx_user_file_object_stream_by_file_uuid,
)

dcx_api_routes_users_me_file_object_router = APIRouter(prefix="/users", tags=["users"])


@dcx_api_routes_users_me_file_object_router.get(
    "/me/files/{file_uuid}",
    response_model=None,
)
def get_authenticated_dcx_user_file_object(
    request: Request,
    file_uuid: str,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session is active.
        - file_uuid identifies one private file object owned by the authenticated user.
      postconditions:
        - Returns the file bytes as an inline HTTP response when the file is visible.
        - Returns a canonical JSON error wrapper when the file is missing or unreadable.
      side_effects:
        - performs one backend storage read
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The app needs private preview/download URLs that do not expose internal message or storage
          structure.
        - Browser media elements and open-in-new-tab downloads do not reliably include an Origin
          header, so this read-only route relies on session authentication plus ownership checks.
      WHEN TO USE it:
        - Use it from authenticated app surfaces when rendering private file attachments.
      WHEN NOT TO USE it:
        - Do not use it for public files or admin cross-user inspection.
      WHAT CAN GO WRONG:
        - The session can be missing.
        - The file UUID can be invalid or belong to another user.
        - The backing object can be missing from storage.
      WHAT COMES NEXT:
        - Future signed-delivery or shared-user grants can sit behind this same flat file boundary.

    TESTS:
      - users_me_file_object_route_returns_stream_for_authenticated_session
      - users_me_file_object_route_allows_media_element_request_without_origin

    ERRORS:
      - API_USERS_ME_FILE_OBJECT_NOT_FOUND:
          suggested_action: Refresh the file view and retry with one current file.
          common_causes:
            - wrong file UUID
            - file belongs to another user
            - file is not active
          recovery_steps:
            - Refresh the Messages view.
            - Retry with one visible file.
          retry_safe: true
      - API_USERS_ME_FILE_OBJECT_READ_FAILED:
          suggested_action: Retry after confirming backend storage is healthy.
          common_causes:
            - missing R2 object
            - storage outage
          recovery_steps:
            - Confirm R2 health and file presence.
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
        file_stream = read_authenticated_dcx_user_file_object_stream_by_file_uuid(
            authenticated_user_id=authenticated_user_id,
            file_uuid=file_uuid,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_FILE_OBJECT_READ_FAILED",
                    "message": "We could not load that file right now.",
                    "suggested_action": "Retry in a moment after the backend storage layer is healthy.",
                },
            },
        )

    if file_stream is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_FILE_OBJECT_NOT_FOUND",
                    "message": "That file does not exist for this account.",
                    "suggested_action": "Refresh the file view and retry with one visible file.",
                },
            },
        )

    return _build_dcx_private_file_response(
        request=request,
        content_bytes=file_stream["content_bytes"],
        content_type=file_stream["content_type"],
        original_filename=file_stream["original_filename"],
    )


def _build_dcx_private_file_response(
    request: Request,
    content_bytes: bytes,
    content_type: str,
    original_filename: str,
) -> Response:
    shared_headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{original_filename}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }

    range_header = request.headers.get("range")
    if not range_header:
        return Response(
            content=content_bytes,
            media_type=content_type,
            headers={
                **shared_headers,
                "Content-Length": str(len(content_bytes)),
            },
        )

    parsed_range = _read_dcx_http_single_byte_range(
        range_header=range_header,
        content_length=len(content_bytes),
    )
    if parsed_range is None:
        return Response(
            status_code=416,
            media_type=content_type,
            headers={
                **shared_headers,
                "Content-Range": f"bytes */{len(content_bytes)}",
            },
        )

    start_byte, end_byte = parsed_range
    partial_content = content_bytes[start_byte : end_byte + 1]
    return Response(
        content=partial_content,
        status_code=206,
        media_type=content_type,
        headers={
            **shared_headers,
            "Content-Length": str(len(partial_content)),
            "Content-Range": f"bytes {start_byte}-{end_byte}/{len(content_bytes)}",
        },
    )


def _read_dcx_http_single_byte_range(range_header: str, content_length: int) -> tuple[int, int] | None:
    if content_length <= 0:
        return None
    normalized_header = range_header.strip().lower()
    if not normalized_header.startswith("bytes=") or "," in normalized_header:
        return None

    range_value = normalized_header.removeprefix("bytes=").strip()
    if "-" not in range_value:
        return None
    start_text, end_text = range_value.split("-", 1)

    try:
        if start_text == "":
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None
            return (max(content_length - suffix_length, 0), content_length - 1)

        start_byte = int(start_text)
        end_byte = int(end_text) if end_text != "" else content_length - 1
    except ValueError:
        return None

    if start_byte < 0 or end_byte < start_byte or start_byte >= content_length:
        return None

    return (start_byte, min(end_byte, content_length - 1))
