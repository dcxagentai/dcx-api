# Context

Prepared newsletter sends were being marked failed, but the stored recipient failure reason was only:

- `API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED`

That made local operator debugging unnecessarily blind because the underlying provider exception was lost.

# What Changed

- `content/newsletter_sends/dispatch_one_due_dcx_newsletter_send_via_resend.py`
  - now preserves the underlying provider exception type/message when a `RuntimeError` has a chained cause
  - now stores the richer failure string in `stephen_dcx_emails_sends_recipients.failure_reason`
  - now returns `failed_recipient_reasons` in the dispatched-send payload from the capability / one-pass script

# Why This Helps

- Local manual dispatch runs can now tell us what Resend actually rejected.
- The admin summary can still stay high-level, while the terminal or DB inspection can show the underlying provider complaint.

# Verification

- `pytest content/newsletter_sends/dispatch_one_due_dcx_newsletter_send_via_resend_test.py`
