"""
CONTEXT:
This file owns the admin HTTP boundary that prepares one DCX newsletter send.
It exists so the admin newsletters editor can stage recipient snapshots and tracked links before the
background delivery worker is connected.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.newsletter_sends.prepare_dcx_admin_newsletter_send import (
    prepare_dcx_admin_newsletter_send_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_newsletter_send_prepare_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminPrepareNewsletterSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled_send_at_ts_ms: int | None = None


@dcx_api_routes_admin_content_newsletter_send_prepare_router.post(
    "/content/newsletters/{language_code}/{email_key}/sends/prepare",
    response_model=None,
)
def post_dcx_admin_content_newsletter_send_prepare(
    request: Request,
    language_code: str,
    email_key: str,
    prepare_request: DcxAdminPrepareNewsletterSendRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The browser origin is one allowed DCX frontend origin.
        - The path identifies one live newsletter row.
      postconditions:
        - Returns a canonical success wrapper for one newly prepared newsletter send.
      side_effects:
        - creates one send row
        - creates recipient snapshot rows
        - creates tracked-link rows
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - Internal users need to stage newsletter sends before the real delivery worker exists.
      WHEN TO USE it:
        - Use it for `prepare now` and `prepare scheduled send` actions.
      WHEN NOT TO USE it:
        - Do not use it for actual provider dispatch yet.
      WHAT CAN GO WRONG:
        - The newsletter can be missing.
        - The database can be unavailable.
      WHAT COMES NEXT:
        - The prepared send appears in the sends catalog and can later be dispatched or cancelled.

    TESTS:
      - covered_indirectly_by_prepare_newsletter_send_capability_tests

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_SEND_SOURCE_NOT_FOUND:
          suggested_action: Refresh the newsletters list and retry from the current live row.
          common_causes:
            - stale newsletter route
            - newsletter no longer live
          recovery_steps:
            - Reload the newsletters catalog.
            - Retry from the live row.
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
        prepared_send = prepare_dcx_admin_newsletter_send_capability(
            authenticated_admin_user_id=authenticated_admin_user_id,
            email_key=email_key,
            language_code=language_code,
            scheduled_send_at_ts_ms=prepare_request.scheduled_send_at_ts_ms,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = 404 if error_code == "API_DCX_ADMIN_NEWSLETTER_SEND_SOURCE_NOT_FOUND" else 500
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not prepare that newsletter send.",
                    "suggested_action": "Refresh the newsletter route and retry after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": prepared_send,
        "context": {
            "surface": "admin",
            "view": "newsletter_send_prepare",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
