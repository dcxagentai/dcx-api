"""
CONTEXT:
This file is the cron-friendly entrypoint for queued DCX AI translation jobs.
"""

from __future__ import annotations

import json
import os

from admin.translations.process_due_dcx_admin_ai_translation_jobs import (
    process_due_dcx_admin_ai_translation_jobs_capability,
)


def run_due_dcx_ai_translation_jobs() -> dict:
    return process_due_dcx_admin_ai_translation_jobs_capability(
        max_jobs=_read_max_translation_jobs_per_run(),
    )


def _read_max_translation_jobs_per_run() -> int:
    raw_value = os.getenv("DCX_AI_TRANSLATION_MAX_JOBS_PER_RUN", "12")
    try:
        parsed_value = int(raw_value)
    except ValueError:
        return 12
    return max(1, min(parsed_value, 25))


if __name__ == "__main__":
    print(json.dumps(run_due_dcx_ai_translation_jobs(), sort_keys=True))
