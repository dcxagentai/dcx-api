## Context

This follow-up tightened the new Resend adapter after reviewing the sender configuration behavior.

The earlier adapter shape still had hardcoded sender fallbacks:
- `DCX`
- `onboarding@resend.dev`

That was too permissive for the current backend standard because missing provider configuration should fail loudly and be fixed explicitly, not silently fall back to a hardcoded sender identity.

## What Changed

The low-level provider adapter in:
- `apis/resend/send_email.py`

now requires all of these env values to be present and non-empty:
- `RESEND_API_KEY`
- `DCX_EMAIL_SIGNUP_RESEND_FROM_NAME`
- `DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL`

If any are missing, it now raises:
- `API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING`

instead of silently defaulting the sender name or sender email.

The adapter was also simplified structurally so it is more locally complete:
- removed the two tiny private helper methods
- inlined config reads, missing-config checks, Resend payload shaping, and the send call into the one main method
- made the missing-config error string include the actual missing env var names

Example shape now:
- `API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:RESEND_API_KEY`
- `API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:DCX_EMAIL_SIGNUP_RESEND_FROM_EMAIL`

The signup and resend route modules were updated so this new configuration error is treated as a normal provider-configuration failure path.

After that, the adapter was tightened one more step so its declared contract and actual behavior match more closely:
- the contract now names all required env vars explicitly
- the code now validates that `email_delivery_draft` contains non-empty `recipient_email`, `subject`, and `text_body`
- malformed drafts now raise:
  - `API_PUBLIC_EMAIL_SIGNUP_RESEND_DRAFT_INVALID:<missing_fields>`
- the `API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED` error declaration now includes:
  - `what_changed`
  - `rollback_needed`
  - `rollback_operation`

This brought the file more in line with the active error-handling instructions:
- explicit preconditions
- stable error codes
- actionable recovery guidance
- extra rollback context when side effects may already have started

The transactional email module narratives were also updated to match the stricter requirement, and `.env.example` now states clearly that all three Resend values are required.

## Verification

Ran the backend test suite from the repo-local virtualenv after the change.

Result:
- `50 passed in 1.04s`

## Outcome

The backend no longer sends anything using hardcoded sender fallbacks.

If sender configuration is incomplete, the failure is now explicit and fixable through environment configuration.
