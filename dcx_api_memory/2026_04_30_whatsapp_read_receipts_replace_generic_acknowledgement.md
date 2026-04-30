# 2026_04_30_whatsapp_read_receipts_replace_generic_acknowledgement

## Summary

After Slice 1 passed app, email, and WhatsApp smoke tests, the WhatsApp chat still showed a generic
`Received. I'm analysing this now.` bubble after each inbound message. That was useful during early
ingest testing, but noisy for investor-facing WhatsApp use.

We replaced that generic outbound acknowledgement with the native Meta WhatsApp read-receipt call.
Inbound WhatsApp messages are now quietly marked as read using the provider message id, while real
workflow follow-ups such as trade candidate review links continue to send actual WhatsApp text.

## Files

- `apis/meta_whatsapp/mark_dcx_meta_whatsapp_inbound_message_as_read.py`
- `apis/meta_whatsapp/mark_dcx_meta_whatsapp_inbound_message_as_read_test.py`
- `apis/meta_whatsapp/read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload.py`
- `messages/process_dcx_meta_whatsapp_inbound_webhook_payload.py`
- `messages/process_dcx_meta_whatsapp_inbound_webhook_payload_test.py`
- `routes/public/dcx_api_routes_public_meta_whatsapp_webhooks.py`
- `routes/public/dcx_api_routes_public_meta_whatsapp_webhooks_test.py`

## Behavior

- Inbound WhatsApp envelopes now carry `should_mark_read: true`.
- The webhook processor calls Meta with:
  - `messaging_product: "whatsapp"`
  - `status: "read"`
  - `message_id: <inbound provider message id>`
- The processor records `read_receipt_status` in its returned diagnostic payload.
- Generic receipt text is no longer sent.
- Trade candidate follow-up messages are unchanged.

## Verification

- `python -m pytest messages/process_dcx_meta_whatsapp_inbound_webhook_payload_test.py apis/meta_whatsapp/mark_dcx_meta_whatsapp_inbound_message_as_read_test.py apis/meta_whatsapp/read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload_test.py routes/public/dcx_api_routes_public_meta_whatsapp_webhooks_test.py -q`
- `python -m py_compile apis/meta_whatsapp/mark_dcx_meta_whatsapp_inbound_message_as_read.py messages/process_dcx_meta_whatsapp_inbound_webhook_payload.py apis/meta_whatsapp/read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload.py routes/public/dcx_api_routes_public_meta_whatsapp_webhooks.py`

## Next

After deploy, send one WhatsApp text and one image into the live callback. The expected user-facing
chat behavior is: the inbound user message receives WhatsApp read ticks, no separate generic DCX
acknowledgement bubble appears, and any trade candidate still receives the trade review link.
