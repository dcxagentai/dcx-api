"""
CONTEXT:
This file runs one DCX newsletter Resend dispatch pass.
It exists so local development and operator smoke tests can dispatch one due newsletter send
without starting the long-running worker loop.
"""

from __future__ import annotations

import sys
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
from content.newsletter_sends.schedule_due_dcx_email_sequence_sends import (
    schedule_due_dcx_email_sequence_sends_capability,
)


def run_one_due_dcx_newsletter_resend_dispatch_pass() -> dict:
    """
    CONTRACT:
      preconditions:
        - The process is running in one backend environment with database and Resend configuration.
      postconditions:
        - Executes exactly one due-send dispatch attempt.
        - Returns the underlying dispatch summary whether one send was claimed or the worker was idle.
      side_effects:
        - may dispatch one due newsletter send through Resend
        - may update newsletter send and recipient delivery rows
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: none
      locks:
        - row-level locking is delegated to the dispatch capability
      contention_strategy: relies on the claim-and-lock strategy inside the dispatch capability

    NARRATIVE:
      WHY this exists:
        - Local testing should have one tiny command that turns a prepared due send into a real provider send.
      WHEN TO USE it:
        - Use it in local development after preparing a newsletter send in the admin UI.
        - Use it for manual smoke tests when one dispatch pass is easier than running a persistent worker.
      WHEN NOT TO USE it:
        - Do not use it as the production background worker command.
        - Do not use it when you need continuous due-send polling.
      WHAT CAN GO WRONG:
        - Missing database or Resend configuration can cause the pass to raise.
        - If no due sends exist, the result will be one idle summary instead of a send.
      WHAT COMES NEXT:
        - The full worker loop remains the right production command.

    TESTS:
      - no direct one-pass entrypoint test exists yet; the dispatch capability owns the falsification layer

    ERRORS:
      - none:
          suggested_action: inspect the raised backend error and worker logs
          common_causes: []
          recovery_steps: []
          retry_safe: true

    CODE:
    """
    sequence_schedule_result = schedule_due_dcx_email_sequence_sends_capability()
    dispatch_result = dispatch_one_due_dcx_newsletter_send_via_resend_capability()
    return {
        "sequence_schedule_result": sequence_schedule_result,
        "dispatch_result": dispatch_result,
    }


if __name__ == "__main__":
    print(run_one_due_dcx_newsletter_resend_dispatch_pass())
