"""
CONTEXT:
This file runs the DCX newsletter Resend dispatch worker loop.
It exists so Render background workers can repeatedly claim and dispatch due newsletter sends
without importing route modules or browser-bound code paths.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def _ensure_dcx_api_repo_root_is_on_python_path() -> None:
    dcx_api_repo_root = Path(__file__).resolve().parents[2]
    dcx_api_repo_root_string = str(dcx_api_repo_root)
    if dcx_api_repo_root_string not in sys.path:
        sys.path.insert(0, dcx_api_repo_root_string)


_ensure_dcx_api_repo_root_is_on_python_path()

from content.newsletter_sends.dispatch_one_due_dcx_newsletter_send_via_resend import (
    dispatch_one_due_dcx_newsletter_send_via_resend_capability,
)


def run_dcx_newsletter_resend_dispatch_worker() -> None:
    """
    CONTRACT:
      preconditions:
        - The process is running in one backend environment with database and Resend configuration.
      postconditions:
        - Repeatedly attempts to dispatch due newsletter sends until the process is stopped.
      side_effects:
        - dispatches newsletter sends through the send-dispatch capability
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Render background workers need one tiny executable entrypoint for newsletter delivery.
      WHEN TO USE it:
        - Use it as the command target for the newsletter background worker process.
      WHEN NOT TO USE it:
        - Do not use it from HTTP routes or interactive admin actions.
      WHAT CAN GO WRONG:
        - Database or provider failures can bubble out of one dispatch pass.
        - A very tight poll interval can create noisy logs or unnecessary database load.
      WHAT COMES NEXT:
        - Later we can add structured logging, metrics, and sequence dispatch on top of the same worker shape.

    TESTS:
      - no direct worker-loop test exists yet; the dispatch capability owns the current falsification layer

    ERRORS:
      - none:
          suggested_action: inspect worker logs
          common_causes: []
          recovery_steps: []
          retry_safe: true

    CODE:
    """
    poll_interval_seconds = _read_worker_poll_interval_seconds()

    while True:
        try:
            dispatch_result = dispatch_one_due_dcx_newsletter_send_via_resend_capability()
            if dispatch_result["status"] == "idle":
                time.sleep(poll_interval_seconds)
        except Exception:
            time.sleep(poll_interval_seconds)


def _read_worker_poll_interval_seconds() -> float:
    raw_value = os.getenv("DCX_NEWSLETTER_DISPATCH_POLL_INTERVAL_SECONDS", "").strip()
    if raw_value == "":
        return 5.0

    try:
        parsed_value = float(raw_value)
    except ValueError:
        return 5.0

    return parsed_value if parsed_value > 0 else 5.0


if __name__ == "__main__":
    run_dcx_newsletter_resend_dispatch_worker()
