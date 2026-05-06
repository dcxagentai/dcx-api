"""
CONTEXT:
This file owns the machine-only HTTP boundary Cloudflare Cron can ping to run due DCX email jobs.
It exists so the existing API service can coordinate scheduled newsletters and sequences without
spinning up a separate Render cron runtime or exposing the job to browser/admin-session auth.
"""

from __future__ import annotations

import os
import secrets
from typing import Any, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

dcx_api_routes_admin_jobs_email_cron_run_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

DCX_CRON_SECRET_HEADER_NAME = "x-dcx-cron-secret"


@dcx_api_routes_admin_jobs_email_cron_run_router.post(
    "/jobs/email-cron/run",
    response_model=None,
)
def post_dcx_admin_jobs_email_cron_run(request: Request):
    """
    CONTRACT:
      preconditions:
        - `DCX_CRON_SECRET` is configured on the API service.
        - Caller sends `X-DCX-CRON-SECRET` matching that configured secret.
      postconditions:
        - Runs the due DCX email job pass and returns its JSON-compatible summary.
      side_effects:
        - may schedule due email sequence rows
        - may update email send and recipient rows
        - may send due emails through Resend
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: underlying email scheduler/dispatcher row locks and unique constraints
      locks:
        - locks are acquired in the underlying email job capabilities
      contention_strategy: duplicate pings are safe because the scheduler and dispatcher claim work using database row locks

    NARRATIVE:
      WHY this exists:
        - Cloudflare Cron should be the lightweight metronome, while the already-running API owns
          database state, Resend credentials, and email job logic.
      WHEN TO USE it:
        - Use it from a scheduled Cloudflare Worker every few minutes.
      WHEN NOT TO USE it:
        - Do not call it from browser UI.
        - Do not expose it without the cron secret.
      WHAT CAN GO WRONG:
        - The cron secret can be missing or wrong.
        - The email job can fail because database or Resend configuration is unhealthy.
      WHAT COMES NEXT:
        - If email volume grows, this route can enqueue work and return immediately while a queue/worker drains jobs.

    TESTS:
      - test_admin_jobs_email_cron_run_requires_cron_secret_configuration
      - test_admin_jobs_email_cron_run_rejects_missing_or_wrong_secret
      - test_admin_jobs_email_cron_run_returns_due_email_job_summary

    ERRORS:
      - API_DCX_CRON_SECRET_NOT_CONFIGURED:
          suggested_action: Add `DCX_CRON_SECRET` to the API service environment before enabling scheduled pings.
          common_causes:
            - env var missing
            - env var empty
          recovery_steps:
            - Set the secret in Render.
            - Deploy/restart the API service.
          retry_safe: true
      - API_DCX_CRON_SECRET_INVALID:
          suggested_action: Confirm the Cloudflare Worker secret matches the API service `DCX_CRON_SECRET`.
          common_causes:
            - missing header
            - stale secret
            - typo
          recovery_steps:
            - Update the Cloudflare Worker secret.
            - Retry the scheduled request.
          retry_safe: true
      - API_DCX_EMAIL_CRON_JOB_FAILED:
          suggested_action: Inspect API logs, database connectivity, due send rows, and Resend configuration.
          common_causes:
            - database unavailable
            - Resend unavailable
            - malformed due send rows
          recovery_steps:
            - Fix backend/provider health.
            - Let the next cron ping retry.
          retry_safe: true

    CODE:
    """
    expected_cron_secret = os.getenv("DCX_CRON_SECRET", "").strip()
    if expected_cron_secret == "":
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_CRON_SECRET_NOT_CONFIGURED",
                    "message": "The DCX cron secret is not configured on the API service.",
                    "suggested_action": "Set DCX_CRON_SECRET before enabling scheduled cron pings.",
                },
            },
        )

    provided_cron_secret = request.headers.get(DCX_CRON_SECRET_HEADER_NAME, "").strip()
    if not secrets.compare_digest(provided_cron_secret, expected_cron_secret):
        return JSONResponse(
            status_code=401,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_CRON_SECRET_INVALID",
                    "message": "The DCX cron secret was missing or invalid.",
                    "suggested_action": "Confirm the Cloudflare Worker secret matches the API service secret.",
                },
            },
        )

    try:
        job_summary = _run_due_dcx_email_jobs()
    except Exception:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_EMAIL_CRON_JOB_FAILED",
                    "message": "The DCX email cron job failed.",
                    "suggested_action": "Inspect API logs, database health, due send rows, and Resend configuration.",
                },
            },
        )

    return {
        "ok": True,
        "data": job_summary,
        "context": {
            "surface": "admin",
            "view": "email_cron_job",
            "auth_mode": "cron_secret",
        },
    }


def _run_due_dcx_email_jobs() -> dict[str, Any]:
    from content.newsletter_sends.run_due_dcx_email_jobs import (
        run_due_dcx_email_jobs,
    )

    return run_due_dcx_email_jobs()
