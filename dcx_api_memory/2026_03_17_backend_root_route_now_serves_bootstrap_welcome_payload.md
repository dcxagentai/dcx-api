The backend bootstrap route shape was simplified so the base API URL itself now returns the welcome payload plus the seeded Postgres test message.

Current behavior in [dcx_api_app.py](/C:/Users/Usuario/Documents/matthew/building/forothers/stephen/dcx/dcx_site/dcx_api/dcx_api_app.py):
- `GET /` now returns:
  - `service_name`
  - `status`
  - `message = "Welcome to the connected DCX MVP shell."`
  - `latest_raw_message` from `dcx_bootstrap_test_messages`
- the extra `/api/bootstrap/welcome` route was removed

Why:
- the production backend will already live on `api.dcx.com`
- so an extra `/api/...` prefix for this first smoke route was unnecessary
- the frontend shared-branding banner can now call the backend base URL directly

Shared branding source was updated accordingly in:
- `dcx_site/dcx_branding/dist/index.jsx`

Important practical note:
- the frontend repos currently consume the published `@prompteoai/dcx-branding` package version
- so this new fetch path will not reach the frontend shells until branding is either:
  - packed locally and temporarily reinstalled into the frontend repos, or
  - published as a new package version and then adopted by the frontend repos

Verification completed after the route simplification:
- focused backend pytest run passed: `13 passed`
- direct in-process request to `GET /` returned the seeded bootstrap message:
  - `preview_text = "Hello from the fresh DCX bootstrap test schema."`
