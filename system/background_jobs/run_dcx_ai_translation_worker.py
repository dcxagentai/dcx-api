"""
CONTEXT:
This file runs the DCX AI translation worker loop.
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

from admin.translations.process_due_dcx_admin_ai_translation_jobs import (
    process_due_dcx_admin_ai_translation_jobs_capability,
)


def run_dcx_ai_translation_worker() -> None:
    poll_interval_seconds = _read_worker_poll_interval_seconds()
    max_jobs_per_pass = _read_worker_max_jobs_per_pass()

    while True:
        try:
            result = process_due_dcx_admin_ai_translation_jobs_capability(
                max_jobs=max_jobs_per_pass,
            )
            if result["status"] == "idle":
                time.sleep(poll_interval_seconds)
        except Exception:
            time.sleep(poll_interval_seconds)


def _read_worker_poll_interval_seconds() -> float:
    raw_value = os.getenv("DCX_AI_TRANSLATION_POLL_INTERVAL_SECONDS", "").strip()
    if raw_value == "":
        return 5.0
    try:
        parsed_value = float(raw_value)
    except ValueError:
        return 5.0
    return parsed_value if parsed_value > 0 else 5.0


def _read_worker_max_jobs_per_pass() -> int:
    raw_value = os.getenv("DCX_AI_TRANSLATION_MAX_JOBS_PER_PASS", "3")
    try:
        parsed_value = int(raw_value)
    except ValueError:
        return 3
    return max(1, min(parsed_value, 25))


if __name__ == "__main__":
    run_dcx_ai_translation_worker()
