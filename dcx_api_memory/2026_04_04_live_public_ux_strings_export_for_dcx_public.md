# 2026_04_04_live_public_ux_strings_export_for_dcx_public

## Context

`dcx_public` needed a way to consume the newly-seeded `stephen_dcx_ux_strings` rows without turning the public Astro site into a per-request database reader.

The chosen midpoint was:

- database is the source of truth
- backend exports live public UX strings into a generated frontend bundle
- Astro builds static language routes from that generated file

## What Changed

Added backend utilities under `languages/`:

- `read_live_dcx_public_ux_strings_bundle.py`
- `read_live_dcx_public_ux_strings_bundle_test.py`
- `export_live_dcx_public_ux_strings_bundle.py`
- `export_live_dcx_public_ux_strings_bundle_test.py`

These utilities:

- read live rows from `stephen_dcx_ux_strings`
- join through `stephen_dcx_languages`
- shape the output as:
  - `language_code -> string_group -> string_key -> text`
- currently export only the public groups needed by the first flow:
  - `home`
  - `signup_form`
  - `signup_otp_page`
  - `signup_otp_form`
  - `signup_confirmation_page`
- currently export only the initial public languages:
  - `en`
  - `es`
  - `fr`
  - `de`

## Important Current Truth

- `dcx_public` now has a generated bundle file that is intended to be refreshed from this exporter whenever live UX-string rows change.
- This keeps the Astro public site static and SEO-friendly while still using the DB-backed multilingual model.
- No admin publish/rebuild automation exists yet; this is still a manual/export-driven first implementation.

## Operational Note

In the local Codex environment, directly invoking the repo-local `.venv\\Scripts\\python.exe` was blocked by Windows access issues, so export was run with the system Python plus repo-local site-packages on `PYTHONPATH`.

That environment quirk is local-tooling-specific, not part of the intended product workflow.
