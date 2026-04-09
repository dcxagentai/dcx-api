Removed the old startup schema-apply hook from `dcx_api_app.py`.

Why:
- the project is currently using explicit manual SQL application on local and live
- the old auth/signup startup schema apply came from an earlier stage
- it created confusion and deployment fragility, especially when Render hit transient database connectivity issues during boot

What changed:
- `dcx_api_app.py` no longer imports or calls `apply_initial_user_signup_schema_to_configured_database`
- FastAPI app startup is now clean and does not attempt schema mutation

Practical consequence:
- schema changes only happen when we intentionally apply SQL ourselves
- Render deploys should no longer fail because of the legacy startup schema step

Context:
- this was prompted by a Render deploy failure during boot while trying to connect to Postgres for the legacy startup schema apply
- that failure likely left `dcx_admin` ahead of `dcx_api`, which explained the live category surface behaving partially updated
