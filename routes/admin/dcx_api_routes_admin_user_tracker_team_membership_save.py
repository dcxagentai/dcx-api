"""
CONTEXT:
This file owns the admin-facing save endpoint for Tracker Team membership.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.users.save_dcx_admin_user_tracker_team_membership import (
    save_dcx_admin_user_tracker_team_membership_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_user_tracker_team_membership_save_router = APIRouter(prefix="/admin", tags=["admin"])


class DcxAdminUserTrackerTeamMembershipSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int
    is_tracker_team_member: bool


@dcx_api_routes_admin_user_tracker_team_membership_save_router.post(
    "/users/tracker-team-membership/save",
    response_model=None,
)
def post_dcx_admin_user_tracker_team_membership_save(
    request: Request,
    tracker_team_membership_save_request: DcxAdminUserTrackerTeamMembershipSaveRequest,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        save_result = save_dcx_admin_user_tracker_team_membership_capability(
            target_user_id=tracker_team_membership_save_request.user_id,
            is_tracker_team_member=tracker_team_membership_save_request.is_tracker_team_member,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=400 if error_code != "API_DCX_ADMIN_USER_TRACKER_TEAM_MEMBERSHIP_SAVE_FAILED" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not save that Tracker Team setting.",
                    "suggested_action": "Refresh the user list and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": save_result,
        "context": {
            "surface": "admin",
            "view": "users_list",
            "operation": "tracker_team_membership_saved",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
