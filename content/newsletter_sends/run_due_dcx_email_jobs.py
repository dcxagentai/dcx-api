"""
CONTEXT:
This file is the Render cron entrypoint for DCX owned email scheduling and sending.
It exists so the MVP can run newsletter and sequence scheduling from DCX's own API repo,
database, and Resend account instead of depending on a third-party scheduler.

FLOW/SYSTEM:
- Render Cron Job checks out the `dcx-api` repo.
- Render runs `python -m content.newsletter_sends.run_due_dcx_email_jobs`.
- This entrypoint schedules at most one due email sequence launch.
- It then dispatches due newsletter/sequence send rows through the existing Resend dispatcher.

CONTRACT:
preconditions:
  - API repo dependencies are installed.
  - Database env variables are present.
  - Resend env variables are present when due sends exist.
  - `DCX_API_BASE_URL` is present for tracked email links.
postconditions:
  - Due sequences may be converted into scheduled send rows.
  - Due newsletter/sequence send rows may be dispatched.
  - A compact JSON summary is printed to stdout for Render logs.
side_effects:
  - writes sequence enrollment and delivery rows
  - updates email sequence rows
  - updates email send and recipient rows
  - sends emails through Resend
idempotent: false
retry_safe: true
async: false
idempotency_key: underlying row locks and unique constraints in the scheduler/dispatcher
locks:
  - row-level locks inside `schedule_due_dcx_email_sequence_sends_capability`
  - row-level locks inside `dispatch_one_due_dcx_newsletter_send_via_resend_capability`
contention_strategy: each capability claims rows with `FOR UPDATE SKIP LOCKED`; parallel cron runs skip rows already being processed

NARRATIVE:
WHY this exists:
  - Render needs one explicit command for the MVP email cron job.
WHEN TO USE it:
  - Use it from Render cron every few minutes.
WHEN NOT TO USE it:
  - Do not call it from request/response HTTP paths.
WHAT CAN GO WRONG:
  - No work may be due, which is a normal idle result.
  - Database or Resend can fail, in which case Render logs the exception and exits non-zero.
WHAT COMES NEXT:
  - If volume grows, replace this simple cron with a queue/worker service while keeping the same domain capabilities.

TESTS:
  - Covered indirectly by focused scheduler and dispatcher tests.
  - Compile smoke via `python -m compileall content/newsletter_sends/run_due_dcx_email_jobs.py`.

ERRORS:
  - API_DCX_EMAIL_CRON_JOB_FAILED:
      suggested_action: Inspect Render logs, database connectivity, due send rows, and Resend configuration.
      common_causes:
        - database unavailable
        - missing Resend env
        - provider error
      recovery_steps:
        - Fix configuration or provider health.
        - Let the next cron run retry due work.
      retry_safe: true
      what_changed: Some sequence/send rows may have changed before failure.
      rollback_needed: inspect_if_partial_send_suspected
      rollback_operation: review `stephen_dcx_emails_sends` and recipient rows before manual replay

CODE:
"""

from __future__ import annotations

import json
import os

from content.newsletter_sends.dispatch_one_due_dcx_newsletter_send_via_resend import (
    dispatch_one_due_dcx_newsletter_send_via_resend_capability,
)
from content.newsletter_sends.schedule_due_dcx_email_sequence_sends import (
    schedule_due_dcx_email_sequence_sends_capability,
)


def run_due_dcx_email_jobs() -> dict:
    max_dispatches_per_run = _read_max_dispatches_per_run()
    sequence_schedule_result = schedule_due_dcx_email_sequence_sends_capability()
    dispatch_results = []

    for _ in range(max_dispatches_per_run):
        dispatch_result = dispatch_one_due_dcx_newsletter_send_via_resend_capability()
        dispatch_results.append(dispatch_result)
        if dispatch_result.get("status") == "idle":
            break

    return {
        "ok": True,
        "sequence_schedule_result": sequence_schedule_result,
        "dispatch_results": dispatch_results,
    }


def _read_max_dispatches_per_run() -> int:
    raw_value = os.getenv("DCX_EMAIL_CRON_MAX_DISPATCHES_PER_RUN", "5")
    try:
        parsed_value = int(raw_value)
    except ValueError:
        return 5

    if parsed_value < 1:
        return 1
    if parsed_value > 25:
        return 25
    return parsed_value


if __name__ == "__main__":
    try:
        print(json.dumps(run_due_dcx_email_jobs(), sort_keys=True))
    except Exception as exc:  # pragma: no cover - Render integration path
        raise RuntimeError("API_DCX_EMAIL_CRON_JOB_FAILED") from exc
