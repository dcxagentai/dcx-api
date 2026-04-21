"""
CONTEXT:
This file owns the admin HTTP boundary that reads the DCX schedule operations catalog.
It exists so the internal schedule route can show one unified list of timed newsletter and sequence work.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.operations.read_dcx_admin_schedule_operations_catalog import (
    read_dcx_admin_schedule_operations_catalog_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_schedule_operations_catalog_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_schedule_operations_catalog_router.get(
    "/operations/schedule",
    response_model=None,
)
def get_dcx_admin_schedule_operations_catalog(request: Request):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    _, identity_resolution_mode, auth_error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request
    )
    if auth_error_response is not None:
        return auth_error_response

    try:
        schedule_catalog = read_dcx_admin_schedule_operations_catalog_capability()
    except RuntimeError as runtime_error:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": str(runtime_error),
                    "message": "We could not load the schedule operations just now.",
                    "suggested_action": "Retry after confirming the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": schedule_catalog,
        "context": {
            "surface": "admin",
            "view": "schedule_operations_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
