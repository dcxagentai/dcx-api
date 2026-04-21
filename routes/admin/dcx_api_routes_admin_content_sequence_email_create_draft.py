"""
CONTEXT:
This file owns the admin-facing sequence-email draft-create HTTP boundary.
It exists so internal users can start one new sequence-email identity before the immutable editor takes over.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.emails.create_dcx_admin_sequence_email_draft import (
    create_dcx_admin_sequence_email_draft_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_sequence_email_create_draft_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminSequenceEmailCreateDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_subject: str
    language_code: str


@dcx_api_routes_admin_content_sequence_email_create_draft_router.post(
    "/content/emails/sequence/create-draft",
    response_model=None,
)
def post_dcx_admin_content_sequence_email_create_draft(
    request: Request,
    sequence_email_create_draft_request: DcxAdminSequenceEmailCreateDraftRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The body contains the initial sequence-email subject and language code.
      postconditions:
        - Creates one new sequence-email draft identity and returns the canonical success wrapper.
      side_effects:
        - inserts one new live sequence-email row
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The sequence-email catalog needs one explicit `New sequence email` action before editing begins.
      WHEN TO USE it:
        - Use it from the admin sequence-emails catalog only.
      WHEN NOT TO USE it:
        - Do not use it to launch sequences or create newsletter identities.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - The input can be invalid.
      WHAT COMES NEXT:
        - The frontend should navigate to the editor route for the returned sequence-email key.

    TESTS:
      - covered_by_sequence_email_draft_capability_tests_and_admin_app_route_integration

    ERRORS:
      - API_DCX_ADMIN_SEQUENCE_EMAIL_DRAFT_INVALID:
          suggested_action: Enter a subject before creating the draft.
          common_causes:
            - blank subject
            - blank language code
          recovery_steps:
            - Fill in the required fields.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        draft_result = create_dcx_admin_sequence_email_draft_capability(
            email_subject=sequence_email_create_draft_request.email_subject,
            language_code=sequence_email_create_draft_request.language_code,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400
            if error_code != "API_DCX_ADMIN_SEQUENCE_EMAIL_DRAFT_CREATE_FAILED"
            else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not create that DCX sequence email draft.",
                    "suggested_action": "Check the draft fields and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": draft_result,
        "context": {
            "surface": "admin",
            "view": "sequence_emails_catalog",
            "operation": "draft_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
