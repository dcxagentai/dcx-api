Context
- We needed the smallest possible proof that `dcx_public` Astro builds can reach `dcx_api` during static generation before refactoring the real public UX-string bundle away from the committed generated TypeScript file.

What changed
- Added a token-gated capability at [read_dcx_public_build_time_api_test_payload.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\public_site\build\read_dcx_public_build_time_api_test_payload.py).
- Added a token-gated route at [dcx_api_routes_public_build_time_api_test.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\routes\public\dcx_api_routes_public_build_time_api_test.py).
- Mounted the route in [dcx_api_app.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\dcx_api_app.py).

Route shape
- `GET /public/build-time/api-test`
- Required header: `X-DCX-Public-Build-Token`
- Required backend env: `DCX_PUBLIC_BUILD_API_TOKEN`

Payload shape
- Success wrapper returns:
  - `build_test_message`
  - `backend_runtime_environment`
  - `issued_at_ts_ms`

Verification
- Focused backend tests passed:
  - [read_dcx_public_build_time_api_test_payload_test.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\public_site\build\read_dcx_public_build_time_api_test_payload_test.py)
  - [dcx_api_routes_public_build_time_api_test_test.py](C:\Users\Usuario\Documents\matthew\building\forothers\stephen\dcx\dcx_site\dcx_api\routes\public\dcx_api_routes_public_build_time_api_test_test.py)

Why this matters
- This proves the secure backend side of Option A without involving the real UX-string bundle or database export path yet.
- The next step can reuse the same token pattern for the real build-time public UX-string bundle route.
