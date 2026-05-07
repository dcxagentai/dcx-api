"""
CONTEXT:
This file owns the admin-facing newsletter detail HTTP boundary.
It exists so the admin frontend can open one stable path-based editor route for one newsletter/language pair.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from admin.content.newsletters.read_dcx_admin_live_newsletter_detail import (
    read_dcx_admin_live_newsletter_detail_capability,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_newsletter_detail_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_newsletter_detail_router.get(
    "/content/newsletters/{language_code}/{email_key}",
    response_model=None,
)
def get_dcx_admin_content_newsletter_detail(
    request: Request,
    language_code: str,
    email_key: str,
    send_audience_scope: str = Query(default="all"),
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The path contains one language code and one newsletter email key.
        - send_audience_scope optionally selects which audience readiness should be calculated against.
      postconditions:
        - Returns a canonical success wrapper containing one live newsletter detail row.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Newsletter editing should use path-based identity routes, not query-string selectors.
      WHEN TO USE it:
        - Use it from the admin `/content/newsletters/<language>/<email_key>` route only.
      WHEN NOT TO USE it:
        - Do not use it for transactional templates or send dispatch.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - The requested live newsletter row may not exist.
      WHAT COMES NEXT:
        - The editor can save later versions through the existing email save route.

    TESTS:
      - covered_indirectly_by_admin_newsletter_detail_route_test

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_DETAIL_NOT_FOUND:
          suggested_action: Return to the newsletters list, refresh it, and reopen the current live row.
          common_causes:
            - stale newsletter route
            - newsletter not yet created in the requested language
          recovery_steps:
            - Reload the newsletters catalog.
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
        newsletter_detail = read_dcx_admin_live_newsletter_detail_capability(
            email_key=email_key,
            language_code=language_code,
            send_audience_scope=send_audience_scope,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = 404 if error_code == "API_DCX_ADMIN_NEWSLETTER_DETAIL_NOT_FOUND" else 500
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not load that DCX newsletter.",
                    "suggested_action": "Return to the newsletters list and retry from the current live row.",
                },
            },
        )

    return {
        "ok": True,
        "data": newsletter_detail,
        "context": {
            "surface": "admin",
            "view": "newsletter_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
