"""
CONTEXT:
This file owns the admin-facing tracker work-item save HTTP boundary.
It exists so the Tracker page can create and edit the nested strategy/operation/battle/task map.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.tracker.save_dcx_admin_tracker_work_item import (
    save_dcx_admin_tracker_work_item_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_tracker_work_item_save_router = APIRouter(prefix="/admin", tags=["admin"])


class DcxAdminTrackerWorkItemSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_item_id: int | None = None
    title: str
    description: str
    current_state: str
    level: str
    pillar: str
    status: str
    parent_work_item_id: int | None = None


@dcx_api_routes_admin_tracker_work_item_save_router.post(
    "/tracker/work-items/save",
    response_model=None,
)
def post_dcx_admin_tracker_work_item_save(
    request: Request,
    work_item_save_request: DcxAdminTrackerWorkItemSaveRequest,
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
        save_result = save_dcx_admin_tracker_work_item_capability(
            acting_admin_user_id=acting_admin_user_id or 0,
            work_item_id=work_item_save_request.work_item_id,
            title=work_item_save_request.title,
            description=work_item_save_request.description,
            current_state=work_item_save_request.current_state,
            level=work_item_save_request.level,
            pillar=work_item_save_request.pillar,
            status=work_item_save_request.status,
            parent_work_item_id=work_item_save_request.parent_work_item_id,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_TRACKER_WORK_ITEM_SAVE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not save that tracker item.",
                    "suggested_action": "Check the tracker fields and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": save_result,
        "context": {
            "surface": "admin",
            "view": "tracker_catalog",
            "operation": "work_item_saved",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
