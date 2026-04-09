"""
CONTEXT:
This file owns the admin-facing content-page category detail HTTP boundary.
It exists so the admin frontend can open one stable path-based editor route for one category/language pair.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.pages.read_dcx_admin_live_content_page_category_detail import (
    read_dcx_admin_live_content_page_category_detail_capability,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_page_category_detail_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_page_category_detail_router.get(
    "/content/page-categories/{language_code}/{category_key}",
    response_model=None,
)
def get_dcx_admin_content_page_category_detail(
    request: Request,
    language_code: str,
    category_key: str,
):
    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        category_detail = read_dcx_admin_live_content_page_category_detail_capability(
            category_key=category_key,
            language_code=language_code,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = (
            404
            if error_code == "API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DETAIL_NOT_FOUND"
            else 400
            if error_code == "API_DCX_ADMIN_CONTENT_PAGE_CATEGORY_DETAIL_INVALID"
            else 500
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not load that DCX content page category.",
                    "suggested_action": "Return to the categories list and retry from the current live row.",
                },
            },
        )

    return {
        "ok": True,
        "data": category_detail,
        "context": {
            "surface": "admin",
            "view": "content_page_category_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
