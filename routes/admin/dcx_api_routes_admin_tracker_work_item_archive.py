"""
CONTEXT:
This file owns the admin-facing tracker work-item archive HTTP boundary.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.tracker.archive_dcx_admin_tracker_work_item import (
    archive_dcx_admin_tracker_work_item_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_tracker_work_item_archive_router = APIRouter(prefix="/admin", tags=["admin"])


class DcxAdminTrackerWorkItemArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_item_id: int
    is_archived: bool


@dcx_api_routes_admin_tracker_work_item_archive_router.post(
    "/tracker/work-items/archive",
    response_model=None,
)
def post_dcx_admin_tracker_work_item_archive(
    request: Request,
    work_item_archive_request: DcxAdminTrackerWorkItemArchiveRequest,
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
        archive_result = archive_dcx_admin_tracker_work_item_capability(
            acting_admin_user_id=acting_admin_user_id or 0,
            work_item_id=work_item_archive_request.work_item_id,
            is_archived=work_item_archive_request.is_archived,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_TRACKER_WORK_ITEM_ARCHIVE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not archive that tracker item.",
                    "suggested_action": "Refresh the tracker and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": archive_result,
        "context": {
            "surface": "admin",
            "view": "tracker_catalog",
            "operation": "work_item_archived",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
