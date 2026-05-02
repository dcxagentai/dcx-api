# Cross-Surface Trade Thread Routing

Date: 2026-05-01

## What changed

Private trade conversations now have the first MVP bridge between the web app, email, and WhatsApp.

The web app remains the canonical conversation surface. When a trader posts in a private trade thread, DCX can notify the other participant via their selected default interaction channel:

- `app_only`
- `email`
- `whatsapp`

Email and WhatsApp notifications include an explicit thread reference such as `#C24`. Inbound email or WhatsApp replies containing that reference are routed into the matching private trade thread instead of being treated as a new trade/topic/other message.

## Backend files

- `users/account/read_authenticated_dcx_user_account_summary.py`
  - exposes `default_interaction_channel`
  - exposes available channel choices for the settings UI

- `users/account/save_authenticated_dcx_user_account_editable_settings.py`
  - validates and stores the user default interaction channel

- `messages/send_dcx_trade_thread_message_notification.py`
  - resolves recipient routing
  - sends trade chat notifications by email or WhatsApp
  - records outbound route metadata for auditability

- `messages/append_authenticated_dcx_trade_thread_message.py`
  - accepts source channel and source contact message metadata
  - sends best-effort notification to the other participant after commit

- `messages/route_dcx_inbound_contact_message_to_trade_thread_if_applicable.py`
  - detects explicit `#C...` references
  - verifies the sender is a participant
  - appends the reply to the correct private trade thread
  - marks the inbound contact message as routed/completed

- `messages/ingest_dcx_contact_message_from_inbound_envelope.py`
  - attempts trade-thread routing before ordinary workflow classification

## Database patch

The schema patch is stored at:

- `storage/dcx_add_cross_surface_trade_thread_routes_2026_05_01.sql`

It adds:

- `stephen_dcx_users.default_interaction_channel`
- `stephen_dcx_trade_thread_participant_routes`
- additional outbound route columns/indexes for trade thread notification/reference tracking

## Smoke tests

1. User A and User B have an open private trade thread.
2. User B sets trade chat notifications to email or WhatsApp.
3. User A posts in the web trade thread.
4. User B receives the notification with a `#C...` reference.
5. User B replies by email/WhatsApp with `#C...` and a message.
6. The reply appears in the web app trade conversation.
7. The inbound message is not classified as a new trade/topic/other message.
8. A non-participant using the same `#C...` reference is not routed into the private thread.

## Notes

This is deliberately explicit-reference MVP routing. It does not yet infer thread continuity from email headers, WhatsApp reply context, or provider conversation metadata.
