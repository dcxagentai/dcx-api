"""
CONTEXT:
This file owns the admin-facing content-page publish HTTP boundary.
It exists so the admin editor can make publish one explicit action on top of immutable page versions.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.pages.publish_dcx_admin_live_content_page_row_version import (
    publish_dcx_admin_live_content_page_row_version_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_page_publish_live_row_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminContentPagePublishLiveRowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: int
    category_key: str
    page_title: str
    page_lede: str
    page_body_markdown: str
    meta_title: str
    meta_description: str
    page_slug: str


@dcx_api_routes_admin_content_page_publish_live_row_router.post(
    "/content/pages/publish-live-row",
    response_model=None,
)
def post_dcx_admin_content_page_publish_live_row(
    request: Request,
    content_page_publish_live_row_request: DcxAdminContentPagePublishLiveRowRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The body contains one current live page row id plus the candidate publish values.
      postconditions:
        - Saves one new immutable published live page row version.
      side_effects:
        - updates one current live content-page row to `is_live = false`
        - inserts one new published live content-page row when content changed
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Publishing should read as one explicit workflow action for the client.
      WHEN TO USE it:
        - Use it from the admin page editor `Publish` action only.
      WHEN NOT TO USE it:
        - Do not use it for ordinary draft autosave.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - The publish content can be invalid or stale.
      WHAT COMES NEXT:
        - The public-site deploy flow can then pick up the published row as pending content.

    TESTS:
      - covered_indirectly_by_admin_content_page_publish_live_row_route_test

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_SAVE_INVALID:
          suggested_action: Refresh the page row and retry with valid content and one unique slug.
          common_causes:
            - blank required fields
            - stale live row id
            - invalid category
            - conflicting slug
          recovery_steps:
            - Refresh the editor.
            - Correct the page content.
            - Retry the publish.
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
        publish_result = publish_dcx_admin_live_content_page_row_version_capability(
            target_page_id=content_page_publish_live_row_request.page_id,
            next_category_key=content_page_publish_live_row_request.category_key,
            next_page_title=content_page_publish_live_row_request.page_title,
            next_page_lede=content_page_publish_live_row_request.page_lede,
            next_page_body_markdown=content_page_publish_live_row_request.page_body_markdown,
            next_meta_title=content_page_publish_live_row_request.meta_title,
            next_meta_description=content_page_publish_live_row_request.meta_description,
            next_page_slug=content_page_publish_live_row_request.page_slug,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_CONTENT_PAGE_SAVE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not publish that DCX content page.",
                    "suggested_action": "Refresh the row and retry with valid content and one unique slug.",
                },
            },
        )

    return {
        "ok": True,
        "data": publish_result,
        "context": {
            "surface": "admin",
            "view": "content_page_detail",
            "operation": "live_row_published",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
