"""
CONTEXT:
This file owns the admin-facing content-page draft-create HTTP boundary.
It exists so internal users can create one new page identity before the autosave editor takes over.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.pages.create_dcx_admin_content_page_draft import (
    create_dcx_admin_content_page_draft_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_page_create_draft_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminContentPageCreateDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_key: str
    page_title: str
    language_code: str


@dcx_api_routes_admin_content_page_create_draft_router.post(
    "/content/pages/create-draft",
    response_model=None,
)
def post_dcx_admin_content_page_create_draft(
    request: Request,
    content_page_create_draft_request: DcxAdminContentPageCreateDraftRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The body contains the target category, initial title, and language code.
      postconditions:
        - Creates one new draft page identity and returns the canonical success wrapper.
      side_effects:
        - inserts one new live content-page row
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The pages list needs one explicit `New page` action before autosave editing begins.
      WHEN TO USE it:
        - Use it from the admin pages list only.
      WHEN NOT TO USE it:
        - Do not use it to create translations or publish existing pages.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - The input can be invalid or the category can be stale.
      WHAT COMES NEXT:
        - The frontend should navigate to the editor route for the returned page key.

    TESTS:
      - covered_indirectly_by_admin_content_page_create_draft_route_test

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as an admin/dev user, then retry.
          common_causes:
            - no authenticated admin/dev session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the admin login screen.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_DRAFT_INVALID:
          suggested_action: Enter a title and choose one valid category before retrying.
          common_causes:
            - blank title
            - blank category
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
        draft_result = create_dcx_admin_content_page_draft_capability(
            category_key=content_page_create_draft_request.category_key,
            page_title=content_page_create_draft_request.page_title,
            language_code=content_page_create_draft_request.language_code,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_CONTENT_PAGE_DRAFT_CREATE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not create that DCX content page draft.",
                    "suggested_action": "Check the draft fields and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": draft_result,
        "context": {
            "surface": "admin",
            "view": "content_pages_catalog",
            "operation": "draft_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
