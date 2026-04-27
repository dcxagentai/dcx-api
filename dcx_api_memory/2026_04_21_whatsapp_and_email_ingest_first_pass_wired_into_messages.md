DCX API memory note
Date: 2026-04-21

Summary
- Wired the first-pass WhatsApp and inbound email intake flows into the same `stephen_dcx_contact_messages` pipeline already used by app-authored messages.
- Kept the shared slice intentionally narrow: text-bearing intake through first derivation only.
- Left media download, OCR, transcription, attachment storage, and broader trade/question classification for the next pass.

What changed
- Mounted the public Meta WhatsApp webhook router in `dcx_api_app.py`, so the GET handshake and POST message webhook are now reachable.
- Updated the public Resend webhook route to branch `email.received` events into inbound-message processing instead of treating them like outbound delivery events.
- Tightened the shared inbound ingest result to expose normalized source/target handles, then used the normalized WhatsApp E.164 value for the acknowledgement send.
- Expanded `.env.example` with:
  - `OPENAI_API_KEY`
  - `DCX_OPENAI_MESSAGE_DERIVATION_MODEL`
  - `META_WHATSAPP_WEBHOOK_VERIFY_TOKEN`
  - `META_APP_SECRET`
  - `META_API_VERSION`
  - `META_PHONE_NUMBER_ID`
  - `META_WHATSAPP_TOKEN`
  - comments for Resend inbound receiving on a custom address like `chat@mail.dcxagent.ai`

What is now true
- App input path:
  - authenticated app route creates canonical message rows
  - derivation runs immediately
  - trader sees the message in Messages
- WhatsApp input path:
  - Meta GET handshake route verifies `hub.verify_token`
  - Meta POST route verifies `X-Hub-Signature-256`
  - verified payload is reduced to inbound message envelopes
  - provider event row is stored
  - canonical message row is stored
  - first derivation runs
  - short WhatsApp acknowledgement text is sent
- Email input path:
  - Resend webhook verification still happens at the public route
  - `email.received` now branches into inbound email processing
  - full received-email content is fetched from Resend's receiving API
  - provider event row is stored
  - canonical message row is stored
  - first derivation runs

What is still deferred on purpose
- WhatsApp media download and storage
- inbound email attachment retrieval and storage
- app file uploads
- OCR, audio transcription, document synthesis
- broader business-intent classification
- deal creation, broadcasts, negotiation threads

Focused verification
- Ran the focused backend pytest slice with the new and existing message/webhook tests.
- Result: `17 passed`
- Warning only: existing Windows `.pytest_cache` create warning, not a functional failure.

Most useful product reading
- The three ingress paths now all converge on the same canonical message domain before any later trade logic.
- That means the next slice can focus on multimodal derivation and classification without needing to redesign the intake model again.
