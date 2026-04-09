"""
CONTEXT:
This file owns the admin-facing newsletter draft-create HTTP boundary.
It exists so internal users can start a new newsletter identity before the immutable editor takes over.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.newsletters.create_dcx_admin_newsletter_draft import (
    create_dcx_admin_newsletter_draft_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_newsletter_create_draft_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminNewsletterCreateDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_subject: str
    language_code: str


@dcx_api_routes_admin_content_newsletter_create_draft_router.post(
    "/content/newsletters/create-draft",
    response_model=None,
)
def post_dcx_admin_content_newsletter_create_draft(
    request: Request,
    newsletter_create_draft_request: DcxAdminNewsletterCreateDraftRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The body contains the initial newsletter subject and language code.
      postconditions:
        - Creates one new newsletter draft identity and returns the canonical success wrapper.
      side_effects:
        - inserts one new live newsletter row
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The newsletters list needs one explicit `New newsletter` action before editing begins.
      WHEN TO USE it:
        - Use it from the admin newsletters list only.
      WHEN NOT TO USE it:
        - Do not use it to send newsletters or create translations.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - The input can be invalid.
      WHAT COMES NEXT:
        - The frontend should navigate to the editor route for the returned newsletter key.

    TESTS:
      - covered_indirectly_by_admin_newsletter_create_draft_route_test

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_DRAFT_INVALID:
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
        draft_result = create_dcx_admin_newsletter_draft_capability(
            email_subject=newsletter_create_draft_request.email_subject,
            language_code=newsletter_create_draft_request.language_code,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_NEWSLETTER_DRAFT_CREATE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not create that DCX newsletter draft.",
                    "suggested_action": "Check the draft fields and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": draft_result,
        "context": {
            "surface": "admin",
            "view": "newsletters_catalog",
            "operation": "draft_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
