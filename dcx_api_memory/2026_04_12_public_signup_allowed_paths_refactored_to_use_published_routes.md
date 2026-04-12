Public email signup no longer relies only on the old hardcoded landing-page path set when validating `signup_page_url`.

What changed:
- Added [read_allowed_public_email_signup_page_paths.py](C:/Users/Usuario/Documents/matthew/building/forothers/stephen/dcx/dcx_site/dcx_api/users/signup_email/read_allowed_public_email_signup_page_paths.py)
- It combines:
  - static localized roots and legacy landing paths
  - live published category routes
  - live published article routes
- Updated [accept_public_email_signup_request.py](C:/Users/Usuario/Documents/matthew/building/forothers/stephen/dcx/dcx_site/dcx_api/users/signup_email/accept_public_email_signup_request.py) to read allowed signup paths dynamically instead of using the old `PUBLIC_EMAIL_SIGNUP_ALLOWED_SIGNUP_PATHS` constant
- Added tests for the new reader and expanded the signup acceptance tests
- Updated [dcx_api_routes_users_signup_email.py](C:/Users/Usuario/Documents/matthew/building/forothers/stephen/dcx/dcx_site/dcx_api/routes/users/dcx_api_routes_users_signup_email.py) so `API_PUBLIC_EMAIL_SIGNUP_ALLOWED_PATHS_UNAVAILABLE` maps to the generic safe browser-facing rejection

Why:
- CORS and public-origin validation should stay env-driven by domain/origin
- Signup source paths should follow the real published public site, not require code/env edits whenever content grows

Important operational note:
- The immediate production failure the user hit was still CORS preflight, caused by `https://dcxagent.ai` missing from `DCX_FRONTEND_ADDITIONAL_ALLOWED_ORIGINS`
- After that env is fixed, this refactor prevents the next likely failure where article/category signup URLs would have been rejected as invalid paths

Verification:
- `py_compile` succeeded on the changed backend files
- repo-local pytest could not be run from this shell because the Windows repo-local venv still returns access denied here
- a direct Python smoke test with minimal stubs confirmed:
  - article signup URLs normalize correctly
  - live category/article paths are derived into the allowlist as expected
