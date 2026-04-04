## Context

This session reorganized `dcx_api/` into a more mature folder structure before the next MVP build phase, while keeping the existing public email signup behavior unchanged.

The guiding goals were:
- reduce root-folder sprawl
- make flow-to-file traceability clearer
- split user signup route steps into separate route files
- keep provider naming down in `apis/`
- move business-purpose email sending up into `emails/transactional/`

## What Changed

### Folder structure

The backend now leans on these top-level folders instead of a flat root:
- `storage/`
- `routes/`
- `users/`
- `emails/`
- `apis/`
- `system/`
- `files/`
- `languages/`
- `llms/`
- `trades/`

Simple `__init__.py` markers were added so the new package boundaries are explicit.

### Users signup flow

The previous grouped users signup route file was replaced by three flow-step route files:
- `routes/users/dcx_api_routes_users_signup_email.py`
- `routes/users/dcx_api_routes_users_signup_email_verify_otp.py`
- `routes/users/dcx_api_routes_users_signup_email_resend_otp.py`

Shared route-edge helper logic now lives in:
- `routes/users/dcx_api_routes_users_support.py`

The underlying signup domain modules were moved under:
- `users/signup_email/`

### Storage and system modules

The old `dcx_storage/` folder was moved to:
- `storage/`

Rate-limit and bootstrap helpers were moved into:
- `system/rate_limits/`
- `system/bootstrap/`

### Email organization

Transactional signup email behavior now follows the domain/provider split more closely:

- domain-level email purpose:
  - `emails/transactional/send_public_email_signup_otp.py`
  - `emails/transactional/send_public_email_signup_confirmation.py`

- provider-specific adapter:
  - `apis/resend/send_email.py`

This keeps `Resend` naming in the provider layer instead of in the main functional filenames.

### Files hello-world route

The R2 smoke-test route now lives under:
- `routes/files/dcx_api_routes_files_r2_hello_world.py`

and the app root imports it from there.

## Behavior Preservation

The intention of this refactor was structural, not behavioral.

The existing public signup flow still uses the same three public endpoints:
- `POST /users/signup-email`
- `POST /users/signup-email/verify-otp`
- `POST /users/signup-email/resend-otp`

The route behavior and minimal browser payloads were kept intact while imports and module locations changed underneath them.

## Verification

Ran the backend test suite from the repo-local virtualenv after the refactor.

Result:
- `47 passed in 0.99s`

## Follow-on Notes

This session intentionally did not rename every legacy `*_capability` function symbol yet. The main win here was:
- folder organization
- route splitting
- file naming
- provider/domain separation

If we want, a later cleanup pass can make internal function names match the new file naming more closely, but that was not necessary to preserve behavior safely in this reorganization pass.
