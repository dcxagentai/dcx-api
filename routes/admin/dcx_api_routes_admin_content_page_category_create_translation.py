"""
CONTEXT:
This file owns the admin-facing content-page category translation-create HTTP boundary.
It exists so the admin CMS can create missing category language rows from the current source row.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.pages.create_dcx_admin_content_page_category_translation import (
    create_dcx_admin_content_page_category_translation_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_page_category_create_translation_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminContentPageCategoryCreateTranslationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_key: str
    source_language_code: str
    target_language_code: str


@dcx_api_routes_admin_content_page_category_create_translation_router.post(
    "/content/page-categories/create-translation",
    response_model=None,
)
def post_dcx_admin_content_page_category_create_translation(
    request: Request,
    content_page_category_create_translation_request: DcxAdminContentPageCategoryCreateTranslationRequest,
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
        translation_result = create_dcx_admin_content_page_category_translation_capability(
            category_key=content_page_category_create_translation_request.category_key,
            source_language_code=content_page_category_create_translation_request.source_language_code,
            target_language_code=content_page_category_create_translation_request.target_language_code,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = (
            409
            if error_code == "API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_ALREADY_EXISTS"
            else 404
            if error_code == "API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_SOURCE_NOT_FOUND"
            else 400
            if error_code == "API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_TRANSLATION_INVALID"
            else 500
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not create that DCX category translation row.",
                    "suggested_action": "Refresh the category detail and retry with one missing target language.",
                },
            },
        )

    return {
        "ok": True,
        "data": translation_result,
        "context": {
            "surface": "admin",
            "view": "content_page_category_detail",
            "operation": "translation_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
