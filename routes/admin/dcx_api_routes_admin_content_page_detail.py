"""
CONTEXT:
This file owns the admin-facing content-page detail HTTP boundary.
It exists so the admin frontend can open one stable path-based editor route for one page/language pair.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.pages.read_dcx_admin_live_content_page_detail import (
    read_dcx_admin_live_content_page_detail_capability,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_page_detail_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_page_detail_router.get(
    "/content/pages/{language_code}/{page_key}",
    response_model=None,
)
def get_dcx_admin_content_page_detail(
    request: Request,
    language_code: str,
    page_key: str,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The path contains one language code and one page key.
      postconditions:
        - Returns a canonical success wrapper containing one live page detail row.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Admin page editing should use path-based identity routes, not query-string selectors.
      WHEN TO USE it:
        - Use it from the admin `/content/pages/<language>/<page_key>` route only.
      WHEN NOT TO USE it:
        - Do not use it for public page rendering.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - The requested live page row may not exist.
      WHAT COMES NEXT:
        - The editor can autosave, publish, or archive the returned row.

    TESTS:
      - covered_indirectly_by_admin_content_page_detail_route_test

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as an admin/dev user, then retry.
          common_causes:
            - no authenticated admin/dev session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the admin login screen.
          retry_safe: true
      - API_DCX_ADMIN_CONTENT_PAGE_DETAIL_NOT_FOUND:
          suggested_action: Return to the pages list, refresh it, and reopen the current live page row.
          common_causes:
            - stale page route
            - page not yet created in the requested language
          recovery_steps:
            - Reload the pages catalog.
            - Retry from the current live row if needed.
          retry_safe: true

    CODE:
    """
    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        page_detail = read_dcx_admin_live_content_page_detail_capability(
            page_key=page_key,
            language_code=language_code,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = 404 if error_code == "API_DCX_ADMIN_CONTENT_PAGE_DETAIL_NOT_FOUND" else 500
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not load that DCX content page.",
                    "suggested_action": "Return to the pages list and retry from the current live row.",
                },
            },
        )

    return {
        "ok": True,
        "data": page_detail,
        "context": {
            "surface": "admin",
            "view": "content_page_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
