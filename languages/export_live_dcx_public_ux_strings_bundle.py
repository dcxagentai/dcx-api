"""
CONTEXT:
This file exports the live public UX strings into one generated TypeScript file inside dcx_public.
It exists so the public Astro frontend can build static language routes from live database copy
without reaching into Postgres at request time.
"""

from __future__ import annotations

import json
from pathlib import Path

from languages.read_live_dcx_public_ux_strings_bundle import (
    read_live_dcx_public_ux_strings_bundle,
)


def export_live_dcx_public_ux_strings_bundle() -> Path:
    """
    CONTRACT:
      preconditions:
        - The dcx_public workspace exists beside dcx_api under the shared dcx_site folder.
        - The live public UX strings can be read from Postgres.
      postconditions:
        - Writes one generated TypeScript file containing the live public UX-string bundle.
        - Returns the absolute path to the generated file.
      side_effects:
        - writes one generated frontend file
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: live public UX-string rows plus the fixed generated output path
      locks: []
      contention_strategy: single-writer export to one deterministic generated file path

    NARRATIVE:
      why:
        - The public site should build from the same UX-string source of truth the database stores.
        - We still want the public frontend to stay static for SEO and route clarity.
      when_to_use:
        - Use this after changing live UX strings for the public frontend.
        - Use it before building or deploying dcx_public.
      when_not_to_use:
        - Do not use it for email-template exports or admin-only strings.
      what_can_go_wrong:
        - The database read can fail.
        - The dcx_public repo path can be missing.
        - The generated output file can be unwritable.
      what_comes_next:
        - Astro pages can import the generated bundle and render static language routes from it.

    TESTS:
      - writes_generated_typescript_bundle_to_the_public_repo

    ERRORS:
      - API_PUBLIC_UX_STRINGS_EXPORT_TARGET_MISSING:
          suggested_action: Confirm dcx_public exists under dcx_site and retry the export.
          common_causes:
            - wrong workspace structure
            - renamed public repo folder
          recovery_steps:
            - Restore or correct the public repo path.
            - Retry the export.
          retry_safe: true
      - API_PUBLIC_UX_STRINGS_EXPORT_WRITE_FAILED:
          suggested_action: Confirm the generated file path is writable and retry the export.
          common_causes:
            - file lock
            - filesystem permission issue
            - invalid generated directory path
          recovery_steps:
            - Fix the filesystem issue and rerun the export.
          retry_safe: true
          what_changed: []
          rollback_needed: false
          rollback_operation: null

    CODE:
    """
    public_repo_generated_directory = (
        Path(__file__).resolve().parents[2]
        / "dcx_public"
        / "src"
        / "generated"
    )
    public_repo_generated_file_path = (
        public_repo_generated_directory
        / "dcx_public_ux_strings_generated.ts"
    )

    if not public_repo_generated_directory.parent.exists():
        raise RuntimeError("API_PUBLIC_UX_STRINGS_EXPORT_TARGET_MISSING")

    bundle = read_live_dcx_public_ux_strings_bundle()
    generated_file_contents = (
        "/**\n"
        " * CONTEXT:\n"
        " * Generated live UX-string bundle for dcx_public.\n"
        " * This file is produced from stephen_dcx_ux_strings and should not be edited by hand.\n"
        " */\n"
        "export const dcx_public_ux_strings_generated = "
        + json.dumps(bundle, ensure_ascii=False, indent=2)
        + " as const\n"
    )

    try:
        public_repo_generated_directory.mkdir(parents=True, exist_ok=True)
        public_repo_generated_file_path.write_text(
            generated_file_contents,
            encoding="utf-8",
        )
    except Exception as exc:  # pragma: no cover - exercised through monkeypatched failure path
        raise RuntimeError("API_PUBLIC_UX_STRINGS_EXPORT_WRITE_FAILED") from exc

    return public_repo_generated_file_path


if __name__ == "__main__":
    export_live_dcx_public_ux_strings_bundle()
