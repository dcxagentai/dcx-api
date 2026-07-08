"""
CONTEXT:
This file owns the admin-facing AI translation job HTTP boundary.
It exists so all translation-aware admin screens can enqueue and poll AI translation jobs
through one route family instead of one endpoint per language or content type.
"""

from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from admin.translations.enqueue_dcx_admin_ai_translation_jobs import (
    enqueue_dcx_admin_ai_translation_jobs_capability,
)
from admin.translations.process_due_dcx_admin_ai_translation_jobs import (
    process_due_dcx_admin_ai_translation_jobs_capability,
)
from admin.translations.read_dcx_admin_ai_translation_jobs import (
    read_dcx_admin_ai_translation_jobs_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_ai_translation_jobs_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

DCX_CRON_SECRET_HEADER_NAME = "x-dcx-cron-secret"


class DcxAdminAiTranslationJobsEnqueueRequest(BaseModel):
    entity_kind: str
    entity_key: str
    source_language_code: str = "en"
    target_language_codes: list[str] | None = None


@dcx_api_routes_admin_ai_translation_jobs_router.post(
    "/translations/ai-jobs",
    response_model=None,
)
def post_dcx_admin_ai_translation_jobs(
    request: Request,
    background_tasks: BackgroundTasks,
    enqueue_request: DcxAdminAiTranslationJobsEnqueueRequest,
):
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_admin_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_admin_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        enqueue_result = enqueue_dcx_admin_ai_translation_jobs_capability(
            authenticated_admin_user_id=authenticated_admin_user_id,
            entity_kind=enqueue_request.entity_kind,
            entity_key=enqueue_request.entity_key,
            source_language_code=enqueue_request.source_language_code,
            target_language_codes=enqueue_request.target_language_codes,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = 400
        if error_code == "API_DCX_ADMIN_AI_TRANSLATION_SOURCE_NOT_FOUND":
            status_code = 404
        elif error_code == "API_DCX_ADMIN_AI_TRANSLATION_ENQUEUE_FAILED":
            status_code = 500
        return _build_translation_error_response(
            status_code=status_code,
            error_code=error_code,
        )

    enqueued_job_count = sum(1 for job in enqueue_result["jobs"] if job["was_enqueued"])
    if enqueued_job_count > 0:
        background_tasks.add_task(
            process_due_dcx_admin_ai_translation_jobs_capability,
            max_jobs=min(max(enqueued_job_count, 1), 25),
        )

    return {
        "ok": True,
        "data": enqueue_result,
        "context": {
            "surface": "admin",
            "view": "ai_translation_jobs",
            "operation": "ai_translation_jobs_enqueued",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_admin_ai_translation_jobs_router.get(
    "/translations/ai-jobs",
    response_model=None,
)
def get_dcx_admin_ai_translation_jobs(
    request: Request,
    entity_kind: str = Query(...),
    entity_key: str = Query(...),
):
    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        jobs_result = read_dcx_admin_ai_translation_jobs_capability(
            entity_kind=entity_kind,
            entity_key=entity_key,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = 400 if error_code == "API_DCX_ADMIN_AI_TRANSLATION_INVALID" else 500
        return _build_translation_error_response(
            status_code=status_code,
            error_code=error_code,
        )

    return {
        "ok": True,
        "data": jobs_result,
        "context": {
            "surface": "admin",
            "view": "ai_translation_jobs",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_admin_ai_translation_jobs_router.post(
    "/jobs/ai-translations/run",
    response_model=None,
)
def post_dcx_admin_ai_translation_jobs_run(
    request: Request,
):
    expected_cron_secret = os.getenv("DCX_CRON_SECRET", "").strip()
    if expected_cron_secret == "":
        return _build_translation_error_response(
            status_code=503,
            error_code="API_DCX_ADMIN_AI_TRANSLATION_CRON_SECRET_NOT_CONFIGURED",
        )

    provided_cron_secret = request.headers.get(DCX_CRON_SECRET_HEADER_NAME, "").strip()
    if not secrets.compare_digest(provided_cron_secret, expected_cron_secret):
        return _build_translation_error_response(
            status_code=401,
            error_code="API_DCX_ADMIN_AI_TRANSLATION_CRON_SECRET_INVALID",
        )

    try:
        job_result = process_due_dcx_admin_ai_translation_jobs_capability()
    except Exception:
        return _build_translation_error_response(
            status_code=500,
            error_code="API_DCX_ADMIN_AI_TRANSLATION_JOB_RUN_FAILED",
        )

    return {
        "ok": True,
        "data": job_result,
        "context": {
            "surface": "admin",
            "view": "ai_translation_jobs",
            "auth_mode": "cron_secret",
        },
    }


def _build_translation_error_response(status_code: int, error_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": _map_translation_error(error_code),
        },
    )


def _map_translation_error(error_code: str) -> dict[str, Any]:
    if error_code == "API_DCX_ADMIN_AI_TRANSLATION_SOURCE_NOT_FOUND":
        return {
            "code": error_code,
            "message": "We could not find the source content to translate.",
            "suggested_action": "Refresh the editor and retry from the current English source row.",
        }
    if error_code in {
        "API_DCX_ADMIN_AI_TRANSLATION_CRON_SECRET_NOT_CONFIGURED",
        "API_DCX_ADMIN_AI_TRANSLATION_CRON_SECRET_INVALID",
    }:
        return {
            "code": error_code,
            "message": "The AI translation worker trigger is not available.",
            "suggested_action": "Check the cron secret configuration before using the machine worker route.",
        }
    return {
        "code": error_code,
        "message": "We could not start or read the AI translation job.",
        "suggested_action": "Retry after confirming the backend, database, and AI provider are healthy.",
    }
