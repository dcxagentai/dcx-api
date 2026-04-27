"""
CONTEXT:
This file owns the authenticated DCX app HTTP boundary for creating one app-originated message.
It exists so the Messages composer can now submit mixed text-plus-file messages in one roundtrip
while still returning the canonical message-detail payload.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from messages.create_authenticated_dcx_app_contact_message import (
    create_authenticated_dcx_app_contact_message,
)
from messages.read_authenticated_dcx_user_contact_message_detail import (
    read_authenticated_dcx_user_contact_message_detail,
)

dcx_api_routes_users_me_messages_create_router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)


@dcx_api_routes_users_me_messages_create_router.post("/me/messages", response_model=None)
async def post_authenticated_dcx_user_message(
    request: Request,
    message_text: str = Form(""),
    message_files: list[UploadFile] | None = File(None),
):
    """
    CONTRACT:
      preconditions:
        - The request comes from one allowed DCX frontend origin.
        - One authenticated DCX app session is active.
        - The request contains either message_text or one or more uploaded files.
      postconditions:
        - Creates one authenticated app-originated message row.
        - Persists any uploaded attachments and returns the canonical message detail payload.
      side_effects:
        - writes to stephen_dcx_contact_messages
        - may write to stephen_dcx_file_objects
        - may write to stephen_dcx_contact_message_attachments
        - may write to derivation tables
      idempotent: false
      retry_safe: false
      async: true
      idempotency_key: null
      locks:
        - delegated to the authenticated message creation capability
      contention_strategy: each browser submit intentionally creates one new inbound app message

    NARRATIVE:
      WHY this exists:
        - The app Messages composer needs one boundary that can accept mixed text-plus-file
          messages without splitting message text and file upload into separate systems.
      WHEN TO USE it:
        - Use it when an authenticated app user submits the Messages composer.
      WHEN NOT TO USE it:
        - Do not use it for inbound provider webhooks.
      WHAT CAN GO WRONG:
        - The session can be missing.
        - The request can contain neither text nor files.
        - A file can be unsupported or too large.
      WHAT COMES NEXT:
        - Future direct-upload and richer composer states can keep this same result shape.

    TESTS:
      - covered by dcx_api_app_test route assertions

    ERRORS:
      - API_USERS_ME_MESSAGE_TEXT_REQUIRED:
          suggested_action: Enter some text or attach one file before sending the message.
          common_causes:
            - blank textarea
            - empty multipart submit
          recovery_steps:
            - Add text or a file.
            - Retry the send.
          retry_safe: true
      - API_USERS_ME_MESSAGE_ATTACHMENT_TOO_LARGE:
          suggested_action: Retry with a file under 10 MB.
          common_causes:
            - selected file exceeds the configured limit
          recovery_steps:
            - Choose a smaller file.
            - Retry the send.
          retry_safe: true
      - API_USERS_ME_MESSAGE_ATTACHMENT_UNSUPPORTED:
          suggested_action: Retry with a supported image, audio, PDF, DOCX, or PPTX file.
          common_causes:
            - unsupported file type
          recovery_steps:
            - Choose a supported file.
            - Retry the send.
          retry_safe: true

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    attachment_inputs = await _read_dcx_users_me_messages_create_attachment_inputs(message_files or [])

    try:
        creation_result = create_authenticated_dcx_app_contact_message(
            authenticated_user_id=authenticated_user_id,
            message_text=message_text,
            attachment_inputs=attachment_inputs,
        )
        message_detail = read_authenticated_dcx_user_contact_message_detail(
            authenticated_user_id=authenticated_user_id,
            message_id=creation_result["message_id"],
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code == "API_AUTHENTICATED_DCX_CONTACT_MESSAGE_TEXT_REQUIRED":
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MESSAGE_TEXT_REQUIRED",
                        "message": "Enter some text or attach one file before sending the message.",
                        "suggested_action": "Type the message content or attach one file, then retry.",
                    },
                },
            )
        if error_code in {
            "API_AUTHENTICATED_DCX_CONTACT_MESSAGE_ATTACHMENT_TOO_LARGE",
            "API_DCX_CONTACT_MESSAGE_ATTACHMENT_TOO_LARGE",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MESSAGE_ATTACHMENT_TOO_LARGE",
                        "message": "That file is too large for this first multimedia pass.",
                        "suggested_action": "Choose a file under 10 MB and retry.",
                    },
                },
            )
        if error_code in {
            "API_AUTHENTICATED_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED",
            "API_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED",
            "API_DCX_CONTACT_MESSAGE_ATTACHMENT_INVALID",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MESSAGE_ATTACHMENT_UNSUPPORTED",
                        "message": "That file type is not supported yet.",
                        "suggested_action": "Retry with an image, audio file, PDF, DOCX, or PPTX file.",
                    },
                },
            )
        if error_code == "API_AUTHENTICATED_DCX_CONTACT_MESSAGE_USER_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MESSAGE_USER_NOT_FOUND",
                        "message": "We could not find that DCX user account.",
                        "suggested_action": "Sign in again and retry after confirming the account still exists.",
                    },
                },
            )
        if error_code == "API_DCX_CONTACT_MESSAGE_ATTACHMENT_STORE_FAILED":
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MESSAGE_ATTACHMENT_STORE_FAILED",
                        "message": "We could not store that file right now.",
                        "suggested_action": "Retry in a moment after storage is healthy.",
                    },
                },
            )
        if error_code == "API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED":
            logger.exception(
                "Authenticated app message analysis failed after create boundary accepted the send."
            )
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_USERS_ME_MESSAGE_ANALYSIS_PROCESS_FAILED",
                        "message": "We stored that message but could not finish processing it right now.",
                        "suggested_action": "Refresh Messages in a moment. If it still shows as failed, retry once the backend analysis service is healthy.",
                    },
                },
            )
        logger.exception(
            "Authenticated app message create boundary failed with runtime code %s.",
            error_code,
        )
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_USERS_ME_MESSAGE_CREATE_FAILED",
                    "message": "We could not send that message right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": message_detail,
        "context": {
            "surface": "app",
            "view": "message_detail",
            "operation": (
                "message_created_ready"
                if creation_result["processing_status"] == "ready"
                else "message_created_failed"
            ),
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


async def _read_dcx_users_me_messages_create_attachment_inputs(
    message_files: list[UploadFile],
) -> list[dict]:
    attachment_inputs: list[dict] = []
    for uploaded_file in message_files:
        attachment_inputs.append(
            {
                "original_filename": uploaded_file.filename,
                "content_type": uploaded_file.content_type,
                "file_bytes": await uploaded_file.read(),
            }
        )
    return attachment_inputs
