# 2026-05-02 - WhatsApp Outbound Status Capture

## Context
During live trade-chat testing, DCX created WhatsApp outbound route rows for thread `C2` and Meta
returned accepted `wamid...` provider message ids, but the user did not see the WhatsApp messages.
This proved the DCX route resolver and Meta send request were working, but we had no durable view
of Meta's later delivery-status webhooks.

## Change
Added Meta WhatsApp outbound status parsing and recording:

- `apis/meta_whatsapp/read_dcx_meta_whatsapp_outbound_status_events_from_webhook_payload.py`
- `messages/record_dcx_meta_whatsapp_outbound_status_event.py`
- wired into `messages/process_dcx_meta_whatsapp_inbound_webhook_payload.py`

No schema change was required. Status data is merged into
`stephen_dcx_outbound_interaction_routes.route_metadata_json` for matching
`provider_type='meta_whatsapp'` and `provider_message_id`.

## Verification
Focused backend checks passed:

- `python -m pytest messages/process_dcx_meta_whatsapp_inbound_webhook_payload_test.py apis/meta_whatsapp/read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload_test.py`
- `python -m compileall messages/process_dcx_meta_whatsapp_inbound_webhook_payload.py messages/record_dcx_meta_whatsapp_outbound_status_event.py apis/meta_whatsapp/read_dcx_meta_whatsapp_outbound_status_events_from_webhook_payload.py`

## Next Live Check
After deploy, send one new trade-thread message to a WhatsApp-default recipient, wait a few seconds,
then inspect:

```sql
SELECT
    id,
    provider_message_id,
    recipient_user_id,
    trade_thread_id,
    route_metadata_json ->> 'latest_provider_status' AS latest_provider_status,
    route_metadata_json ->> 'latest_provider_status_at_ts_ms' AS latest_provider_status_at_ts_ms,
    route_metadata_json -> 'latest_provider_error' AS latest_provider_error,
    route_metadata_json -> 'whatsapp_status_events' AS whatsapp_status_events
FROM stephen_dcx_outbound_interaction_routes
WHERE provider_type = 'meta_whatsapp'
  AND trade_thread_id = 2
ORDER BY id DESC
LIMIT 10;
```

Expected useful outcomes:

- `sent`, `delivered`, or `read`: Meta delivery is working and the issue is likely UX/device/account visibility.
- `failed` plus `latest_provider_error`: provider-side delivery restriction or recipient/account issue.
- no status fields: Meta is not sending status webhooks to this callback or the subscribed webhook fields need checking.
