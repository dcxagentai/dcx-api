## 2026-03-17 Env Based Database Config For Local And Render

### Summary
The backend database config was moved off literal credentials in `db_config.py` and onto environment-variable resolution.

This now supports both:
- local development through a repo-local `.env`
- production deployment on Render through service environment variables

The config was then intentionally simplified further so it only uses:
- `PROMPTEO_DB_URL`
- or explicit DCX variables

It does not try to guess from multiple fallback naming conventions.

### Files Added Or Updated
Updated:
- `dcx_storage/db_config.py`
- `requirements.txt`

Added:
- `.env`
- `.env.example`
- `dcx_storage/db_config_test.py`

### Current Resolution Rules
`dcx_storage/db_config.py` now resolves database config in this order:

1. If `PROMPTEO_DB_URL` exists:
- return `{"dsn": PROMPTEO_DB_URL}`
- this is the cleanest single-variable production path if Render provides or if we manually set it

2. Otherwise, use explicit DCX fields only:
- `PROMPTEO_DB_NAME`
- `PROMPTEO_DB_USER`
- `PROMPTEO_DB_PASSWORD`
- `PROMPTEO_DB_HOST`
- `PROMPTEO_DB_PORT`
- optional `PROMPTEO_DB_SSLMODE`

No other fallback naming conventions are used.

### Local Development Path
A local `.env` now exists in `dcx_api` with the current local values.

Because `.env` is already ignored by `.gitignore`, it should stay local-only.

A safe template is also now present in:
- `.env.example`

### Render Path
For Render, the backend should not rely on the local `.env` file.

Instead, set the service environment variables in Render.

Recommended simplest production approach:
- set `PROMPTEO_DB_URL`

Alternative if using separate variables:
- `PROMPTEO_DB_NAME`
- `PROMPTEO_DB_USER`
- `PROMPTEO_DB_PASSWORD`
- `PROMPTEO_DB_HOST`
- `PROMPTEO_DB_PORT`
- optionally `PROMPTEO_DB_SSLMODE`

### Verification
The backend dependency set now explicitly includes:
- `python-dotenv`

Tests run successfully with the env-based config path included:
- `13 passed`

### Practical Outcome
The backend can now:
- keep local DB credentials out of Python source code
- read from `.env` locally
- read from real Render environment variables in production
- continue using the same `DB_CONFIG` import path elsewhere in the codebase
- avoid ambiguous variable-name fallback behavior
