"""
CONTEXT:
This file owns the admin HTTP boundary that creates one DCX email-sequence draft.
It exists so internal users can start one sequence planning object before editing its metadata and steps.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.email_sequences.create_dcx_admin_email_sequence_draft import (
    create_dcx_admin_email_sequence_draft_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_email_sequence_create_draft_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminEmailSequenceCreateDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_name: str


@dcx_api_routes_admin_content_email_sequence_create_draft_router.post(
    "/content/emails/sequences/create-draft",
    response_model=None,
)
def post_dcx_admin_content_email_sequence_create_draft(
    request: Request,
    create_request: DcxAdminEmailSequenceCreateDraftRequest,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_admin_user_id, identity_resolution_mode, auth_error_response = (
        read_authenticated_dcx_admin_user_id_or_error_response(request=request)
    )
    if auth_error_response is not None:
        return auth_error_response

    try:
        created_sequence = create_dcx_admin_email_sequence_draft_capability(
            authenticated_admin_user_id=authenticated_admin_user_id,
            sequence_name=create_request.sequence_name,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_EMAIL_SEQUENCE_DRAFT_CREATE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not create that email sequence.",
                    "suggested_action": "Check the sequence name and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": created_sequence,
        "context": {
            "surface": "admin",
            "view": "email_sequences_catalog",
            "operation": "draft_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
