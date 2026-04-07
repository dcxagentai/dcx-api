Context
- We had already proven that Cloudflare Pages and local Astro builds could securely call `dcx_api` during static generation with a token-gated proof route.
- The next step was to move the real `dcx_public` UX-string source from the committed generated TypeScript snapshot to a live backend/database read during build time.

What changed
- Added shared build-token validator:
  - [validate_dcx_public_build_api_token.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\public_site\build\validate_dcx_public_build_api_token.py)
- Refactored the proof capability to reuse the shared validator:
  - [read_dcx_public_build_time_api_test_payload.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\public_site\build\read_dcx_public_build_time_api_test_payload.py)
- Added real live public UX-string build-time capability:
  - [read_dcx_public_build_time_ux_strings_bundle.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\public_site\build\read_dcx_public_build_time_ux_strings_bundle.py)
- Added token-gated route:
  - [dcx_api_routes_public_build_time_ux_strings_bundle.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\routes\public\dcx_api_routes_public_build_time_ux_strings_bundle.py)
- Mounted the route in:
  - [dcx_api_app.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_app.py)

Route shape
- `GET /public/build-time/ux-strings-bundle`
- Required header:
  - `X-DCX-Public-Build-Token`
- Success wrapper:
  - `ok: true`
  - `data.bundle`

Source of truth
- The route returns the live bundle from:
  - [read_live_dcx_public_ux_strings_bundle.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\languages\read_live_dcx_public_ux_strings_bundle.py)
- This means the backend/database is now the build-time source of truth for public multilingual copy.

Verification
- Focused backend tests passed:
  - validator tests
  - proof capability/route tests
  - live UX-string bundle capability/route tests
- Total focused result:
  - `17 passed`

Why this matters
- `dcx_public` no longer needs a checked-in generated UX-string snapshot to build from live copy.
- The next admin publish flow can trigger a static rebuild knowing the build will pull current live content from the backend/database.
