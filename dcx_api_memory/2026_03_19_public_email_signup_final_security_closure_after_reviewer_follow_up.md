CONTEXT:
This note records the final security closure work after the last reviewer follow-up on the DCX
public email-signup / OTP flow. It exists so later agents can see which reviewer findings were
still valid after the second pass, how we closed them, and what was re-verified afterwards.

Summary
- One reviewer was still correct about four issues:
  - provider-send failure could still invalidate the previously delivered OTP/link pair
  - the per-recipient send ceiling still depended on a weak `updated_at_ts_ms` approximation
  - test-recipient override still failed open when `DCX_ENVIRONMENT` was unset
  - route IP throttling still trusted `request.client.host` only
- We fixed those properly and reran the full verification suite.

Final Backend Changes
- `dcx_api_create_or_refresh_public_email_signup_artifacts_capability.py`
  - for fresh sends on an existing challenge, the capability now carries a full recovery snapshot:
    - prior OTP hash/salt
    - prior token hash/expiry
    - prior attempts/counters/cooldown/lock values
    - prior send-budget window state
  - for first-send provider failures on a brand-new challenge, recovery now deletes the unsent row instead of leaving rotated unsent state behind
  - replaced the old `updated_at_ts_ms` send-budget approximation with explicit fixed-window state on the challenge row:
    - `send_budget_window_started_at_ts_ms`
    - `send_budget_request_count`
- `dcx_api_resend_public_email_signup_otp_capability.py`
  - now uses the same explicit fixed-window send-budget state
  - now returns a full prior-state recovery snapshot so a failed resend restores the previously delivered OTP/link state exactly
- `dcx_api_reset_public_email_signup_send_cooldown_after_delivery_failure_capability.py`
  - no longer only clears cooldown
  - now either:
    - deletes a newly created unsent challenge, or
    - restores the full prior mutable challenge state
- `dcx_api_send_public_email_signup_otp_via_resend_capability.py`
  - test-recipient override now requires:
    - `DCX_ENVIRONMENT` explicitly set to `local` or `development`
    - `DCX_EMAIL_SIGNUP_ALLOW_TEST_RECIPIENT_OVERRIDE=true`
  - unset environment now fails closed
- `routes/users/dcx_api_users_signup_email_routes.py`
  - route IP extraction now supports trusted proxy headers only when `DCX_TRUST_PROXY_HEADERS=true`
  - otherwise continues to use `request.client.host`

Schema Change
- `dcx_storage/dcx_initial_user_signup_schema_2026_03_18.sql`
  - added:
    - `send_budget_window_started_at_ts_ms`
    - `send_budget_request_count`

Verification
- backend pytest: `43 passed`
- frontend vitest: `12 passed`
- Astro build: `8 page(s) built`

Current Security Position
- The previously highlighted high issue around failed sends invalidating the last delivered OTP/link is now closed.
- The recipient send budget no longer depends on `updated_at_ts_ms`.
- Test-recipient override is stricter and now fails closed when runtime env is unspecified.
- Proxy-header trust is now explicit instead of implicit.

Residual Follow-up
- The active browser token still lands in `sessionStorage` after fragment capture.
  - This is acceptable for now, but deployment-level CSP/XSS hardening still matters.
- Postgres route-rate-limit rows still need a future pruning strategy.
