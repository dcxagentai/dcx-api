"""
CONTEXT:
This file owns the admin-facing content-page category save HTTP boundary.
It exists so the category editor can autosave or explicitly save durable immutable category versions.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.pages.save_dcx_admin_live_content_page_category_row_version import (
    save_dcx_admin_live_content_page_category_row_version_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_page_category_save_live_row_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminContentPageCategorySaveLiveRowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: int
    category_name: str
    category_description: str
    category_slug: str


@dcx_api_routes_admin_content_page_category_save_live_row_router.post(
    "/content/page-categories/save-live-row",
    response_model=None,
)
def post_dcx_admin_content_page_category_save_live_row(
    request: Request,
    content_page_category_save_live_row_request: DcxAdminContentPageCategorySaveLiveRowRequest,
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
        save_result = save_dcx_admin_live_content_page_category_row_version_capability(
            target_category_id=content_page_category_save_live_row_request.category_id,
            next_category_name=content_page_category_save_live_row_request.category_name,
            next_category_description=content_page_category_save_live_row_request.category_description,
            next_category_slug=content_page_category_save_live_row_request.category_slug,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = (
            404
            if error_code == "API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_LIVE_ROW_NOT_FOUND"
            else 400
            if error_code == "API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_SAVE_INVALID"
            else 500
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not save that DCX content page category.",
                    "suggested_action": "Refresh the row and retry with valid content and one unique slug.",
                },
            },
        )

    return {
        "ok": True,
        "data": save_result,
        "context": {
            "surface": "admin",
            "view": "content_page_category_detail",
            "operation": "save_live_row",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
