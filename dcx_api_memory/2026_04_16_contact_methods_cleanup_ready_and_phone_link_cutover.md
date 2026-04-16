The contact-method refactor is now far enough along that the remaining legacy `stephen_dcx_users` contact columns are only present for deployment-order compatibility, not because the live app/admin/auth/newsletter logic still needs them as the source of truth.

What changed in this slice
- Authenticated session reads now trust the primary email contact method directly, without falling back to `stephen_dcx_users.primary_email`.
- Account summary reads now trust primary email and primary phone contact methods plus linked provider identities directly, without falling back to legacy email/phone user columns.
- Admin user-list reads now trust the primary email contact method directly.
- Newsletter readiness and newsletter-send preparation now read recipient emails and verification state from primary email contact methods instead of `stephen_dcx_users.primary_email*`.
- Editable account settings now do one direct `UPDATE stephen_dcx_users` for mutable settings instead of carrying legacy email snapshot columns through an upsert-shaped write.
- Public signup create and email-OTP verify now use a small runtime schema bridge: if legacy email columns still exist on `stephen_dcx_users`, they keep those snapshots in sync; if the columns are gone, the flow continues using only user row metadata plus contact methods and auth identities.
- WhatsApp phone-link prepare now creates/reuses an unverified `phone` contact method and checks conflicts there instead of using legacy phone columns.
- WhatsApp phone-link verify now marks the phone contact method verified/primary and links the WhatsApp auth identity through `contact_method_id` instead of writing `primary_phone_*` fields on `stephen_dcx_users`.

Why this matters
- We can now drop the legacy contact columns from `stephen_dcx_users` in a coordinated SQL step after the new code is live.
- The normalized model is now the real runtime source of truth for email and phone across auth, account, admin, and newsletter mechanics.

Validation completed in this session
- `py_compile` passed on the changed backend files and the updated focused tests.
- Inline smoke checks passed for:
  - public signup artifact creation
  - public signup OTP verify
  - WhatsApp phone-link OTP prepare
  - WhatsApp phone-link OTP verify
  - editable account settings save
- The desktop shell still cannot spawn the repo venv Python directly due the same Windows access-denied issue seen earlier, so full pytest should still be run from the user shell before/after deploy.

Remaining next steps
- Push this backend slice to live.
- Run the manual focused pytest command from the normal user shell.
- After deploy, run the cleanup SQL that drops:
  - `primary_email`
  - `primary_email_confirmed`
  - `primary_email_confirmed_at_ts_ms`
  - `primary_phone_e164`
  - `primary_phone_confirmed`
  - `primary_phone_confirmed_at_ts_ms`
  - `primary_phone_channel`
- Then move into the next WhatsApp step: replacing the temporary OTP delivery path with the approved Meta verification-template flow, still targeting contact methods and linked auth identities.
