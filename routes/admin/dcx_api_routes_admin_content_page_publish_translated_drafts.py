"""
CONTEXT:
This file owns the admin-facing bulk publish boundary for content-page translations.
It exists so the page editor can promote all existing translated draft rows for one page key
without asking the admin to open every language one by one.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.pages.publish_dcx_admin_content_page_translated_drafts import (
    publish_dcx_admin_content_page_translated_drafts_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_page_publish_translated_drafts_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminContentPagePublishTranslatedDraftsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_key: str


@dcx_api_routes_admin_content_page_publish_translated_drafts_router.post(
    "/content/pages/publish-translated-drafts",
    response_model=None,
)
def post_dcx_admin_content_page_publish_translated_drafts(
    request: Request,
    content_page_publish_translated_drafts_request: DcxAdminContentPagePublishTranslatedDraftsRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The body contains one current page key.
      postconditions:
        - Publishes all current live non-original draft rows for that page key.
        - Returns no-op when there are no draft translations left to publish.
      side_effects:
        - updates zero or more current live content-page translation rows to `is_live = false`
        - inserts zero or more published live content-page translation rows
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The translation flow produces drafts by design, but page route smoke testing needs a single
          publish control for the generated language set.
      WHEN TO USE it:
        - Use it from the admin page editor after translation jobs have created draft translation rows.
      WHEN NOT TO USE it:
        - Do not use it to create translations or trigger the public Astro rebuild.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - The page key can be stale.
        - A translated draft can have a slug conflict.
      WHAT COMES NEXT:
        - The admin can trigger the public-site publish action so Astro rebuilds the new routes.

    TESTS:
      - covered_by_publish_dcx_admin_content_page_translated_drafts_test

    ERRORS:
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_PUBLISH_INVALID:
          suggested_action: Reopen the page from the pages list and retry.
          common_causes:
            - blank page key
          recovery_steps:
            - Refresh the editor.
            - Retry from one valid page row.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_NOT_FOUND:
          suggested_action: Return to the pages list and reopen the current page.
          common_causes:
            - stale page key
          recovery_steps:
            - Reload the pages catalog.
            - Retry from a current page row.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_CONFLICT:
          suggested_action: Inspect the draft translation slugs and retry after resolving conflicts.
          common_causes:
            - duplicate live route in the same language
          recovery_steps:
            - Change the conflicting draft slug or archive the conflicting page.
            - Retry the bulk publish.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_PUBLISH_FAILED:
          suggested_action: Retry once the backend/database are healthy.
          common_causes:
            - database unavailable
            - write failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
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
        publish_result = publish_dcx_admin_content_page_translated_drafts_capability(
            page_key=content_page_publish_translated_drafts_request.page_key,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=500
            if error_code == "API_DCX_ADMIN_CONTENT_PAGE_TRANSLATED_DRAFTS_PUBLISH_FAILED"
            else 400,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not publish the translated draft pages.",
                    "suggested_action": "Refresh the page and retry after checking the translated draft rows.",
                },
            },
        )

    return {
        "ok": True,
        "data": publish_result,
        "context": {
            "surface": "admin",
            "view": "content_page_detail",
            "operation": "translated_drafts_published",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
