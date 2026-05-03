# 2026-05-02 - Cross-Surface Trade Chat WhatsApp Lessons And Next Steps

## Context
We finished the first working MVP pass of private trade chats across the web app, with notification
bridges toward WhatsApp and email. Live testing focused on a trade chat thread (`C2`) where one
participant had `default_interaction_channel = whatsapp`.

The initial symptom was that messages sent in the web app appeared in the web app thread, but did
not appear on WhatsApp. We needed to determine whether the problem was DCX routing, contact lookup,
Meta send acceptance, or WhatsApp policy delivery.

## What We Learned
DCX routing was working.

Live database checks showed:

- `stephen_dcx_trade_threads` correctly had thread `C2`.
- User `BigBanana` had `default_interaction_channel = whatsapp`.
- `stephen_dcx_outbound_interaction_routes` had rows for the trade-thread notifications.
- Those rows had real Meta `wamid...` provider message ids.

That meant:

- DCX selected WhatsApp as the outbound route.
- DCX found a verified WhatsApp-linked phone contact method.
- Meta accepted the outbound send request.

The actual blocker was WhatsApp's 24-hour customer-service window.

After adding outbound WhatsApp status capture, Meta returned:

```text
code: 131047
title: Re-engagement message
details: Message failed to send because more than 24 hours have passed since the customer last replied to this number.
```

Then we sent an ordinary inbound WhatsApp activation message from the phone:

```text
Lets activate the 24 hour whatsapp window
```

That reopened the customer-service window. After that, DCX trade-chat notifications started arriving
on WhatsApp correctly. Replies using the explicit thread reference, such as:

```text
#C2 In that case, we can keep in touch. Perhaps chat more on Monday next week.
```

were routed back into the correct private trade chat, persisted in the web app, and translated for
the other participant.

## Current Working State
As of this note:

- Web app private trade chats work.
- Multiple participants can post into a private trade chat.
- Messages persist on reload.
- Web app polling makes conversations update responsively.
- Cross-language trade-chat messages are translated for the recipient.
- The UI displays translated text plus a compact original-language block.
- WhatsApp trade-chat notification sends work inside the active 24-hour window.
- WhatsApp replies can route into the correct trade chat using `#C2`-style explicit thread references.
- WhatsApp inbound activation messages are ingested and classified as `other`, which is acceptable for MVP.
- Outbound WhatsApp status webhooks are now captured into
  `stephen_dcx_outbound_interaction_routes.route_metadata_json`.

## Files Added Or Changed For Status Diagnosis

- `apis/meta_whatsapp/read_dcx_meta_whatsapp_outbound_status_events_from_webhook_payload.py`
- `messages/record_dcx_meta_whatsapp_outbound_status_event.py`
- `messages/process_dcx_meta_whatsapp_inbound_webhook_payload.py`
- `messages/process_dcx_meta_whatsapp_inbound_webhook_payload_test.py`

The useful diagnostic query is:

```sql
SELECT
    id,
    provider_message_id,
    recipient_user_id,
    trade_thread_id,
    route_metadata_json ->> 'latest_provider_status' AS latest_provider_status,
    route_metadata_json -> 'latest_provider_error' AS latest_provider_error,
    route_metadata_json -> 'whatsapp_status_events' AS whatsapp_status_events
FROM stephen_dcx_outbound_interaction_routes
WHERE provider_type = 'meta_whatsapp'
  AND trade_thread_id = 2
ORDER BY id DESC
LIMIT 10;
```

## Template Proposal For Production
For real client use, WhatsApp notifications outside the 24-hour window require an approved template.

Suggested Meta WhatsApp template:

```text
name: dcx_trade_chat_notification
category: UTILITY
language: en

body:
You have a new DCX trade chat message.

Trade chat: {{1}}
From: {{2}}

Open DCX to review and reply:
{{3}}
```

Variables:

- `{{1}}`: thread reference, e.g. `C2`
- `{{2}}`: sender label, e.g. `@BigBanana` or `Trader #19`
- `{{3}}`: clean app thread URL, e.g. `https://app.dcxagent.ai/me/trade-threads/2`

Why this should be acceptable:

- It is utility/transactional.
- It is triggered by an existing product conversation.
- It does not contain marketing language.
- It avoids detailed sensitive trade terms in the template body.

## Recommended Tomorrow Work

1. Polish the WhatsApp trade-chat notification text used inside the 24-hour free-text window.
2. Submit the `dcx_trade_chat_notification` template in Meta.
3. Add a template send function for trade-chat notifications.
4. Add route logic:
   - If recipient's last inbound WhatsApp message is inside 24 hours, use free text.
   - If outside 24 hours, use the approved template.
   - If template sending fails, record the failure and optionally fall back to email/app-only.
5. Consider surfacing outbound notification health in admin or developer diagnostics.
6. Add a lightweight "last inbound WhatsApp timestamp" helper from existing stored contact messages or provider events.
7. Polish reply instructions:
   - Keep explicit references like `#C2`.
   - Use them for WhatsApp/email replies where provider-native reply threading cannot be trusted.

## Strategic Lesson
The cross-surface architecture is basically right:

- canonical private trade conversation lives in DCX
- WhatsApp/email/web are surfaces into the same conversation
- explicit thread references provide robust fallback routing
- translations happen on the canonical stored message path

The important WhatsApp-specific rule is that "Meta accepted" does not mean "delivered"; delivery
policy status must be captured and acted on.
