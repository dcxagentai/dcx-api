"""
CONTEXT:
This file owns the admin HTTP boundary that cancels one prepared DCX newsletter send row.
It exists so the admin newsletters editor can reverse scheduled send preparation before the
future delivery worker runs.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.newsletter_sends.cancel_dcx_admin_newsletter_send import (
    cancel_dcx_admin_newsletter_send_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_newsletter_send_cancel_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_newsletter_send_cancel_router.post(
    "/content/newsletters/sends/{email_send_id}/cancel",
    response_model=None,
)
def post_dcx_admin_content_newsletter_send_cancel(
    request: Request,
    email_send_id: int,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The browser origin is one allowed DCX frontend origin.
        - email_send_id identifies one prepared send row.
      postconditions:
        - Returns a canonical success wrapper for one cancelled prepared send.
      side_effects:
        - updates one prepared send row
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - Internal users should be able to reverse scheduled send preparation without deleting history.
      WHEN TO USE it:
        - Use it from the prepared sends list for rows still in `scheduled` state.
      WHEN NOT TO USE it:
        - Do not use it after provider sending has started.
      WHAT CAN GO WRONG:
        - The send can be missing or already non-cancellable.
      WHAT COMES NEXT:
        - The future dispatcher will skip cancelled sends.

    TESTS:
      - covered_indirectly_by_cancel_newsletter_send_capability_tests

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_SEND_CANCEL_NOT_ALLOWED:
          suggested_action: Refresh the prepared sends list and retry only on rows still marked scheduled.
          common_causes:
            - row missing
            - already cancelled
            - moved beyond scheduled
          recovery_steps:
            - Reload the sends list.
            - Retry only if the row is still scheduled.
          retry_safe: true

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_admin_user_id, identity_resolution_mode, auth_error_response = (
        read_authenticated_dcx_admin_user_id_or_error_response(request=request)
    )
    if auth_error_response is not None:
        return auth_error_response

    try:
        cancelled_send = cancel_dcx_admin_newsletter_send_capability(
            authenticated_admin_user_id=authenticated_admin_user_id,
            email_send_id=email_send_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = 409 if error_code == "API_DCX_ADMIN_NEWSLETTER_SEND_CANCEL_NOT_ALLOWED" else 500
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not cancel that prepared newsletter send.",
                    "suggested_action": "Refresh the prepared sends list and retry on one scheduled row.",
                },
            },
        )

    return {
        "ok": True,
        "data": cancelled_send,
        "context": {
            "surface": "admin",
            "view": "newsletter_send_cancel",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
