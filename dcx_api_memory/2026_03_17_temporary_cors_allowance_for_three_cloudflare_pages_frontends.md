The backend CORS rule in `dcx_api_app.py` was temporarily widened so the first Cloudflare Pages plumbing proof can reach the Render backend without waiting for the fuller security policy from the other project.

Current temporary allowlist shape:
- local development:
  - `http://localhost:*`
  - `http://127.0.0.1:*`
- Cloudflare Pages MVP hosts:
  - `https://dcx-admin.pages.dev`
  - `https://dcx-app.pages.dev`
  - `https://dcx-public.pages.dev`

Implementation detail:
- this is currently expressed as one `allow_origin_regex` in FastAPI `CORSMiddleware`

Reason:
- the frontend deploys were succeeding
- the backend was healthy on Render
- browser fetches from Pages were failing because the old CORS rule only allowed localhost origins

Verification:
- focused backend route tests passed after the change, including a test for `https://dcx-admin.pages.dev`

Future intent:
- replace this temporary MVP rule with the stricter CORS/XSS/cross-origin policy from the other project once the basic frontend production plumbing is fully proven
