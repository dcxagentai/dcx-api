"""
CONTEXT:
This file owns the first admin-facing email-template save HTTP boundary.
It exists so the admin frontend can autosave one selected live email row into a new
immutable version while placeholder safety and version history stay enforced.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)
from admin.content.emails.save_dcx_admin_live_email_row_version import (
    save_dcx_admin_live_email_row_version_capability,
)

dcx_api_routes_admin_content_emails_save_live_row_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminContentEmailsSaveLiveRowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_id: int
    email_subject: str
    email_body: str


@dcx_api_routes_admin_content_emails_save_live_row_router.post(
    "/content/emails/save-live-row",
    response_model=None,
)
def post_dcx_admin_content_emails_save_live_row(
    request: Request,
    emails_save_live_row_request: DcxAdminContentEmailsSaveLiveRowRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The body contains one current live email row id plus the candidate edited subject and body values.
      postconditions:
        - Saves one new immutable live row version or returns a no-op when the content is unchanged.
        - Returns a canonical success wrapper with the save result metadata.
      side_effects:
        - updates one current live email row to `is_live = false`
        - inserts one new live email row when the content changed
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first admin email editor needs one precise autosave endpoint without exposing direct table writes.
      WHEN TO USE it:
        - Use it from the selected-language email panel only.
      WHEN NOT TO USE it:
        - Do not use it to create new email identities, delete content, or send outbound email.
      WHAT CAN GO WRONG:
        - No authenticated admin/dev session is present.
        - The target row can be stale.
        - The edited content can be blank.
        - Required placeholders can be missing or malformed.
        - Database writes can fail.
      WHAT COMES NEXT:
        - Keep this save route stable while more authenticated translation tooling grows around it.

    TESTS:
      - test_admin_emails_save_live_row_route_returns_save_result_for_authenticated_admin_session
      - test_admin_emails_save_live_row_route_returns_auth_required_without_authenticated_session

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Sign in as an admin/dev user, then retry.
          common_causes:
            - no authenticated admin/dev session cookie
            - expired or revoked session
          recovery_steps:
            - Sign in again through the admin login screen.
          retry_safe: true
      - API_DCX_ADMIN_EMAIL_SAVE_INVALID:
          suggested_action: Refresh the selected row and retry with valid content and exact placeholder tokens.
          common_causes:
            - blank subject or body
            - stale live row id
            - malformed placeholder contract
          recovery_steps:
            - Refresh the catalog.
            - Correct the edited content and retry.
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
        save_result = save_dcx_admin_live_email_row_version_capability(
            target_email_id=emails_save_live_row_request.email_id,
            next_email_subject=emails_save_live_row_request.email_subject,
            next_email_body=emails_save_live_row_request.email_body,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)

        if error_code in {
            "API_DCX_ADMIN_EMAIL_TEMPLATE_CONTENT_INVALID",
            "API_DCX_ADMIN_EMAIL_LIVE_ROW_NOT_FOUND",
            "API_DCX_ADMIN_EMAIL_TEMPLATE_PLACEHOLDER_INVALID",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_DCX_ADMIN_EMAIL_SAVE_INVALID",
                        "message": "We could not save that email template row.",
                        "suggested_action": "Refresh the row and retry with valid content and exact placeholder tokens.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_EMAIL_SAVE_FAILED",
                    "message": "We could not save the DCX email template row just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": save_result,
        "context": {
            "surface": "admin",
            "view": "emails_catalog",
            "operation": "live_row_saved",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
