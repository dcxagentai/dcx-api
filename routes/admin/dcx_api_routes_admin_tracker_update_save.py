"""
CONTEXT:
This file owns the admin-facing tracker update-save HTTP boundary.
It exists so activity updates can be corrected after posting.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.tracker.save_dcx_admin_tracker_update import (
    save_dcx_admin_tracker_update_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_tracker_update_save_router = APIRouter(prefix="/admin", tags=["admin"])


class DcxAdminTrackerUpdateSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_id: int
    work_item_id: int
    update_kind: str
    update_body: str


@dcx_api_routes_admin_tracker_update_save_router.post(
    "/tracker/updates/save",
    response_model=None,
)
def post_dcx_admin_tracker_update_save(
    request: Request,
    update_save_request: DcxAdminTrackerUpdateSaveRequest,
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
        save_result = save_dcx_admin_tracker_update_capability(
            acting_admin_user_id=acting_admin_user_id or 0,
            update_id=update_save_request.update_id,
            work_item_id=update_save_request.work_item_id,
            update_kind=update_save_request.update_kind,
            update_body=update_save_request.update_body,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_TRACKER_UPDATE_SAVE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not save that tracker update.",
                    "suggested_action": "Check the update fields and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": save_result,
        "context": {
            "surface": "admin",
            "view": "tracker_catalog",
            "operation": "update_saved",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
