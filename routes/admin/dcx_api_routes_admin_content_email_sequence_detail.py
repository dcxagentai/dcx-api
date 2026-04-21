"""
CONTEXT:
This file owns the admin HTTP boundary that reads one DCX email-sequence detail payload.
It exists so the admin frontend can open one sequence route and load its metadata and ordered steps.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.email_sequences.read_dcx_admin_email_sequence_detail import (
    read_dcx_admin_email_sequence_detail_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_email_sequence_detail_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_email_sequence_detail_router.get(
    "/content/emails/sequences/{sequence_key}",
    response_model=None,
)
def get_dcx_admin_content_email_sequence_detail(
    request: Request,
    sequence_key: str,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    _, identity_resolution_mode, auth_error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request
    )
    if auth_error_response is not None:
        return auth_error_response

    try:
        sequence_detail = read_dcx_admin_email_sequence_detail_capability(sequence_key=sequence_key)
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=404 if error_code == "API_DCX_ADMIN_EMAIL_SEQUENCE_DETAIL_NOT_FOUND" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not load that email sequence.",
                    "suggested_action": "Refresh the sequences list and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": sequence_detail,
        "context": {
            "surface": "admin",
            "view": "email_sequence_detail",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
