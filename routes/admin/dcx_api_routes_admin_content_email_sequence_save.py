"""
CONTEXT:
This file owns the admin HTTP boundary that saves one DCX email sequence and its steps.
It exists so the sequence editor can persist one coherent planning payload through one write contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.email_sequences.save_dcx_admin_email_sequence_and_steps import (
    save_dcx_admin_email_sequence_and_steps_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_email_sequence_save_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminEmailSequenceStepSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_key: str = ""
    step_name: str
    source_email_id: int
    delay_minutes_from_trigger: int
    is_active: bool = True


class DcxAdminEmailSequenceSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_name: str
    sequence_type: str
    audience_type: str
    trigger_type: str
    scheduled_launch_at_ts_ms: int | None = None
    is_live: bool
    steps: list[DcxAdminEmailSequenceStepSaveRequest]


@dcx_api_routes_admin_content_email_sequence_save_router.post(
    "/content/emails/sequences/{sequence_key}/save",
    response_model=None,
)
def post_dcx_admin_content_email_sequence_save(
    request: Request,
    sequence_key: str,
    save_request: DcxAdminEmailSequenceSaveRequest,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_admin_user_id, identity_resolution_mode, auth_error_response = (
        read_authenticated_dcx_admin_user_id_or_error_response(request=request)
    )
    if auth_error_response is not None:
        return auth_error_response

    try:
        saved_sequence = save_dcx_admin_email_sequence_and_steps_capability(
            authenticated_admin_user_id=authenticated_admin_user_id,
            sequence_key=sequence_key,
            sequence_name=save_request.sequence_name,
            sequence_type=save_request.sequence_type,
            audience_type=save_request.audience_type,
            trigger_type=save_request.trigger_type,
            scheduled_launch_at_ts_ms=save_request.scheduled_launch_at_ts_ms,
            is_live=save_request.is_live,
            steps=[step.model_dump() for step in save_request.steps],
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        return JSONResponse(
            status_code=404 if error_code == "API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_NOT_FOUND" else 400 if error_code == "API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID" else 500,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not save that email sequence.",
                    "suggested_action": "Review the sequence fields and retry once the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": saved_sequence,
        "context": {
            "surface": "admin",
            "view": "email_sequence_detail",
            "operation": "saved",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
