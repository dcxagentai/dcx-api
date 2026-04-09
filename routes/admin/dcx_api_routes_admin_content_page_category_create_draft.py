"""
CONTEXT:
This file owns the admin-facing content-page category draft-create HTTP boundary.
It exists so internal users can create one new category identity before the category editor takes over.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.pages.create_dcx_admin_content_page_category_draft import (
    create_dcx_admin_content_page_category_draft_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_page_category_create_draft_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminContentPageCategoryCreateDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_name: str
    language_code: str


@dcx_api_routes_admin_content_page_category_create_draft_router.post(
    "/content/page-categories/create-draft",
    response_model=None,
)
def post_dcx_admin_content_page_category_create_draft(
    request: Request,
    content_page_category_create_draft_request: DcxAdminContentPageCategoryCreateDraftRequest,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        draft_result = create_dcx_admin_content_page_category_draft_capability(
            category_name=content_page_category_create_draft_request.category_name,
            language_code=content_page_category_create_draft_request.language_code,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DRAFT_CREATE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not create that DCX content page category.",
                    "suggested_action": "Check the category fields and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": draft_result,
        "context": {
            "surface": "admin",
            "view": "content_page_categories_catalog",
            "operation": "draft_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
