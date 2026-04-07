"""
CONTEXT:
This file owns the first admin-facing emails content HTTP boundary.
It exists so the admin frontend can browse multilingual email-template rows without editing them yet.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)
from admin.content.emails.read_dcx_admin_live_emails_catalog import (
    read_dcx_admin_live_emails_catalog_capability,
)

dcx_api_routes_admin_content_emails_catalog_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_emails_catalog_router.get(
    "/content/emails/catalog",
    response_model=None,
)
def get_dcx_admin_content_emails_catalog(
    request: Request,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
      postconditions:
        - Returns a canonical success wrapper containing the live email-template catalog.
        - Returns a canonical error wrapper when no authenticated admin/dev session is available.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first admin content viewer should let internal users inspect multilingual email
          templates directly from the durable content table before CRUD is added.
      WHEN TO USE it:
        - Use it from the read-only admin emails viewer only.
      WHEN NOT TO USE it:
        - Do not treat this as the final admin authorization design.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - Database reads can fail.
      WHAT COMES NEXT:
        - Keep this read contract stable while more authenticated admin tools reuse the same session gate.

    TESTS:
      - test_admin_emails_catalog_route_returns_payload_for_authenticated_admin_session

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as an admin/dev user, then retry.
          common_causes:
            - no authenticated admin/dev session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the admin login screen.
          retry_safe: true
      - API_DCX_ADMIN_EMAILS_CATALOG_READ_FAILED:
          suggested_action: Retry after backend/database health is restored.
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
        emails_catalog = read_dcx_admin_live_emails_catalog_capability()
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_EMAILS_CATALOG_READ_FAILED",
                    "message": "We could not load the live DCX emails catalog just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": emails_catalog,
        "context": {
            "surface": "admin",
            "view": "emails_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
