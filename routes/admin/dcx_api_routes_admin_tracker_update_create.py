"""
CONTEXT:
This file owns the admin-facing tracker update-create HTTP boundary.
It exists so every work item can carry its own activity log as people move it forward.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.tracker.create_dcx_admin_tracker_update import (
    create_dcx_admin_tracker_update_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_tracker_update_create_router = APIRouter(prefix="/admin", tags=["admin"])


class DcxAdminTrackerUpdateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_kind: str
    update_body: str


@dcx_api_routes_admin_tracker_update_create_router.post(
    "/tracker/work-items/{work_item_id}/updates/create",
    response_model=None,
)
def post_dcx_admin_tracker_update_create(
    request: Request,
    work_item_id: int,
    update_create_request: DcxAdminTrackerUpdateCreateRequest,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    acting_admin_user_id, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        create_result = create_dcx_admin_tracker_update_capability(
            acting_admin_user_id=acting_admin_user_id or 0,
            work_item_id=work_item_id,
            update_kind=update_create_request.update_kind,
            update_body=update_create_request.update_body,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_TRACKER_UPDATE_CREATE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not add that tracker update.",
                    "suggested_action": "Choose an existing tracker item, write a non-empty update, and retry.",
                },
            },
        )

    return {
        "ok": True,
        "data": create_result,
        "context": {
            "surface": "admin",
            "view": "tracker_catalog",
            "operation": "update_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
