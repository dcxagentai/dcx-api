Password setup/reset app links now target path-based localized auth routes instead of query-based language routing.

Previous shape:

- `https://app.dcxagent.ai/password/set?mode=password_reset&language_code=fr#password_challenge_token=...`

New shape:

- `https://app.dcxagent.ai/fr/t/password/set?mode=password_reset#password_challenge_token=...`

Why:

- logged-out auth UX should take language from explicit route state
- this reduces reliance on browser-stored language after logout
- it aligns app auth route semantics with the multilingual public-site model

Files updated in this pass:

- `auth/password/dcx_password_link_challenge_support.py`
- `auth/password/create_or_refresh_dcx_password_link_challenge_test.py`

Verification:

- focused password-link challenge tests passed
