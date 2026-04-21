"""
CONTEXT:
This file owns the admin HTTP boundary that reads the DCX email-sequences catalog.
It exists so the admin sequence workspace can load one canonical list of sequence planning rows.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.email_sequences.read_dcx_admin_email_sequences_catalog import (
    read_dcx_admin_email_sequences_catalog_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_email_sequences_catalog_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_email_sequences_catalog_router.get(
    "/content/emails/sequences/catalog",
    response_model=None,
)
def get_dcx_admin_content_email_sequences_catalog(request: Request):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    _, identity_resolution_mode, auth_error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request
    )
    if auth_error_response is not None:
        return auth_error_response

    try:
        sequences_catalog = read_dcx_admin_email_sequences_catalog_capability()
    except RuntimeError as runtime_error:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": str(runtime_error),
                    "message": "We could not load the email-sequences catalog.",
                    "suggested_action": "Retry after confirming the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": sequences_catalog,
        "context": {
            "surface": "admin",
            "view": "email_sequences_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
