CONTEXT:
Slice 1 trade UX now treats trade state as one trader-facing concept while retaining the existing trade identity/version storage split.

WHAT CHANGED:
- `messages/update_authenticated_dcx_user_trade_candidate_details.py` now accepts `draft` and `under_revision` as trade confirmation states.
- `watching` was removed from accepted trade lifecycle statuses because it is not functionally used in Slice 1.
- `messages/read_authenticated_dcx_user_messages_inbox.py` now treats `draft`, `pending_confirmation`, `needs_more_detail`, and `under_revision` trade versions as needing trader attention.
- `storage/dcx_update_trade_single_visible_state_constraints_2026_04_30.sql` updates the local/live check constraints to match the new single visible state model.
- The Slice 1 UX seed file now contains the new trade form labels and state labels in English, Spanish, French, and German.

FOLLOW-UP:
- Run the new constraint migration before testing the app save flow for `Draft` or `Under revision`.
- Rerun the Slice 1 UX seed after the migration so frontend copy resolves from the shared UX string table.
