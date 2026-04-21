Sequence-email lane and sequence-source validation landed in this slice.

What changed:
- Added `admin/content/emails/create_dcx_admin_sequence_email_draft.py` plus its test so admin can create first-class `sequence` email rows in `stephen_dcx_emails`.
- Added `routes/admin/dcx_api_routes_admin_content_sequence_email_create_draft.py` and wired it into `dcx_api_app.py`.
- Broadened the generic managed-email save path so `sequence` drafts can keep an empty body during early drafting, matching the looser newsletter draft behavior.
- Tightened `save_dcx_admin_email_sequence_and_steps.py` so sequence steps must reference live original `sequence` emails, not arbitrary newsletter/transactional rows.
- Generalized the managed-email translation route/capability wording so the existing non-newsletter translation flow now cleanly covers both transactional and sequence emails.

Why this matters:
- The admin surface can now treat sequence content as its own lane instead of a filter over transactional/newsletter content.
- The backend rule now matches the frontend intent: sequence steps are backed by sequence-email content only.

Verification:
- Focused pytest slice passed:
  - `admin/content/emails/create_dcx_admin_sequence_email_draft_test.py`
  - `admin/content/emails/save_dcx_admin_live_email_row_version_test.py`
  - `admin/content/email_sequences/save_dcx_admin_email_sequence_and_steps_test.py`
- Result: `13 passed`

What still comes next:
- Sequence-email translations currently reuse the generic non-newsletter translation route; this is fine for now, but a later polish pass could rename that route/copy more explicitly around “managed emails”.
- Sequence dispatch/runtime plumbing is still later work; this slice only established the content lane and stronger save validation.
