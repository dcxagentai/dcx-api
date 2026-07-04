"""
CONTEXT:
This file owns the admin-facing tracker catalog HTTP boundary.
It exists so the Tracker page can read all work items and recent activity in one request.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.tracker.read_dcx_admin_tracker_catalog import (
    read_dcx_admin_tracker_catalog_capability,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_tracker_catalog_router = APIRouter(prefix="/admin", tags=["admin"])


@dcx_api_routes_admin_tracker_catalog_router.get("/tracker/catalog", response_model=None)
def get_dcx_admin_tracker_catalog(request: Request):
    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        tracker_catalog = read_dcx_admin_tracker_catalog_capability()
    except RuntimeError as runtime_error:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": str(runtime_error),
                    "message": "We could not load the DCX tracker just now.",
                    "suggested_action": "Apply the tracker migration if needed, then retry when the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": tracker_catalog,
        "context": {
            "surface": "admin",
            "view": "tracker_catalog",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
