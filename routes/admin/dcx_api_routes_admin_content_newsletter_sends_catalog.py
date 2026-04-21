"""
CONTEXT:
This file owns the admin HTTP boundary for newsletter send rows in the DCX admin workspace.
It exists so the newsletter editor can show scheduled, dispatched, cancelled, and provider-updated
newsletter send rows without using query-string selectors.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.newsletter_sends.read_dcx_admin_newsletter_sends_catalog import (
    read_dcx_admin_newsletter_sends_catalog_capability,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_newsletter_sends_catalog_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_newsletter_sends_catalog_router.get(
    "/content/newsletters/{language_code}/{email_key}/sends",
    response_model=None,
)
def get_dcx_admin_content_newsletter_sends_catalog(
    request: Request,
    language_code: str,
    email_key: str,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The path contains one language code and one newsletter key.
      postconditions:
        - Returns a canonical success wrapper containing the newsletter-send catalog for that newsletter.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin newsletter editor should show send history and current operational state beside
          the content editor.
      WHEN TO USE it:
        - Use it from the admin newsletter editor route only.
      WHEN NOT TO USE it:
        - Do not use it for recipient-level audit detail.
      WHAT CAN GO WRONG:
        - The database can be unavailable.
      WHAT COMES NEXT:
        - The editor can offer prepare/cancel actions against these rows and show provider outcomes.

    TESTS:
      - covered_indirectly_by_newsletter_sends_catalog_capability_tests

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_SENDS_CATALOG_READ_FAILED:
          suggested_action: Retry after the backend and database are healthy.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify backend/database health.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        sends_catalog = read_dcx_admin_newsletter_sends_catalog_capability(
            email_key=email_key,
            language_code=language_code,
        )
    except RuntimeError as runtime_error:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": str(runtime_error),
                    "message": "We could not load the newsletter send rows.",
                    "suggested_action": "Retry after the backend and database are healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": sends_catalog,
        "context": {
            "surface": "admin",
            "view": "newsletter_sends_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
