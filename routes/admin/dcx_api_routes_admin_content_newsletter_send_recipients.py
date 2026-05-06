"""
CONTEXT:
This file owns the admin HTTP boundary for reading one newsletter send's recipient rows.
It exists so the admin newsletter editor can open a delivery-recipient sheet without exposing
private user messages, trades, topics, attachments, or chat content.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from admin.content.newsletter_sends.read_dcx_admin_newsletter_send_recipients import (
    read_dcx_admin_newsletter_send_recipients_capability,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_newsletter_send_recipients_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_newsletter_send_recipients_router.get(
    "/content/newsletters/sends/{email_send_id}/recipients",
    response_model=None,
)
def get_dcx_admin_content_newsletter_send_recipients(
    request: Request,
    email_send_id: int,
    email_search: str = Query(default=""),
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - email_send_id is one newsletter send id.
        - email_search is optional partial email text.
      postconditions:
        - Returns one canonical success wrapper containing delivery summary and up to 25 recipient rows.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Admin users need to inspect who received a newsletter send and whether delivery succeeded.
      WHEN TO USE it:
        - Use it from the admin newsletter send recipients sheet.
      WHEN NOT TO USE it:
        - Do not use it for content inspection or full-list export.
      WHAT CAN GO WRONG:
        - The database can be unavailable.
      WHAT COMES NEXT:
        - Later versions can add pagination, export, and recipient event timelines.

    TESTS:
      - covered_indirectly_by_newsletter_send_recipients_capability_tests

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_SEND_RECIPIENTS_READ_FAILED:
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
        recipients_payload = read_dcx_admin_newsletter_send_recipients_capability(
            email_send_id=email_send_id,
            email_search=email_search,
        )
    except RuntimeError as runtime_error:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": str(runtime_error),
                    "message": "We could not load the newsletter recipient rows.",
                    "suggested_action": "Retry after the backend and database are healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": recipients_payload,
        "context": {
            "surface": "admin",
            "view": "newsletter_send_recipients",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
