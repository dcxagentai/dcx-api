## 2026-03-17 Bootstrap Test Schema Reset For Backend Plumbing

### Summary
This session reset the backend database proof away from the older alpha-spike table set and onto a fresh minimal one-table bootstrap schema, while preserving an archived copy of the prior alpha create-tables SQL for later reference.

The goal was to make the next local-to-production plumbing step simpler:
- one minimal schema file
- one seeded test message
- one backend read capability
- same frontend-facing payload shape as before

### Archived Alpha Schema
The older alpha create-tables SQL was not living inside `dcx_api`; it was found in the older test workspace and copied into the API repo for reference.

Archived file:
- `dcx_storage/dcx_alpha_schema_archive_from_dcx_test_codex_2026_03_17.sql`

Source preserved from:
- `dcx_test/dcx_test_codex/dcx_test_codex_storage/01_dcx_schema.sql`

### Fresh Minimal Bootstrap Schema
A new minimal schema file was added:
- `dcx_storage/dcx_bootstrap_test_schema_2026_03_17.sql`

It creates exactly one table:
- `dcx_bootstrap_test_messages`

And seeds exactly one stable test row via:
- `message_key = 'bootstrap_hello_world'`
- `channel_type = 'bootstrap'`
- `message_direction = 'system'`
- `text_content = 'Hello from the fresh DCX bootstrap test schema.'`

The seed operation is idempotent through `ON CONFLICT`.

### Schema Apply Capability
A small apply capability was added so the schema can be applied from the configured database connection without depending on a separate psql workflow:
- `dcx_storage/dcx_apply_bootstrap_test_schema_to_configured_database.py`
- adjacent test: `dcx_storage/dcx_apply_bootstrap_test_schema_to_configured_database_test.py`

The command used successfully was:

```powershell
.\.venv\Scripts\python.exe -m dcx_storage.dcx_apply_bootstrap_test_schema_to_configured_database
```

It returned:
- `Applied: dcx_bootstrap_test_schema_2026_03_17.sql (applied)`

### Fresh Read Capability
The backend bootstrap route was moved off the old `dcx_raw_messages` dependency and onto a new read capability:
- `dcx_api_read_latest_bootstrap_test_message_from_local_postgres_capability.py`
- adjacent test: `dcx_api_read_latest_bootstrap_test_message_from_local_postgres_capability_test.py`

Important design choice:
- the capability reads from `dcx_bootstrap_test_messages`
- but it still normalizes the response into the same frontend bootstrap payload shape
- this avoids immediate churn in the shared branding component and three frontends

### FastAPI Route Update
The FastAPI app was updated to import the new bootstrap test capability instead of the old raw-message capability:
- `dcx_api_app.py`

The route path remains the same:
- `/api/bootstrap/welcome`

The frontend-facing response shape still includes:
- `latest_raw_message`

This is intentionally backward-compatible for the frontend bootstrap banner, even though the underlying source table is now the fresh bootstrap test table.

### Verification
The following backend tests were run successfully:

```powershell
.\.venv\Scripts\python.exe -m pytest dcx_storage\dcx_apply_bootstrap_test_schema_to_configured_database_test.py dcx_api_read_latest_bootstrap_test_message_from_local_postgres_capability_test.py dcx_api_app_test.py -q
```

Result:
- `11 passed`

### Practical Meaning
The backend is now in a cleaner state for the first production plumbing proof:
- we no longer depend on the larger alpha raw-message schema just to prove connectivity
- we have a tiny schema that can be recreated locally and later on the first Render Postgres instance
- the three frontends can keep consuming the same bootstrap response shape

### Next Likely Step
Use this fresh bootstrap schema path as the first backend database proof on Render:
1. create Render Postgres instance
2. apply `dcx_bootstrap_test_schema_2026_03_17.sql` or run the Python apply capability against that database
3. point the FastAPI backend at the Render database
4. confirm `/api/bootstrap/welcome` returns the seeded bootstrap row
5. confirm the three frontends render it from production
