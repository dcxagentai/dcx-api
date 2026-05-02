# Trade Chat WhatsApp Notification Route Fix

Date: 2026-05-02

## Finding

Live smoke testing showed that web trade-chat messages appeared instantly in the recipient's web app conversation, but did not send WhatsApp notifications even when the recipient account setting was set to WhatsApp.

This was not expected behavior. The web app being open is not supposed to suppress WhatsApp delivery in this MVP slice.

## Cause

The trade-chat notification resolver required the recipient phone contact method to satisfy:

- active
- verified
- notification-enabled
- linked to a WhatsApp auth identity

The WhatsApp phone-link verification flow deliberately creates/updates verified WhatsApp-linked phone rows with `is_notification_enabled = false`. That made the new trade-chat resolver fail to find a usable WhatsApp route and fall back to app-only/skipped delivery.

## Fix

For explicit trade-chat WhatsApp notification routing, a verified active phone linked to a WhatsApp identity is enough. The user's `default_interaction_channel = 'whatsapp'` is the specific notification preference for this trade-chat surface.

Changed:

- `messages/send_dcx_trade_thread_message_notification.py`
  - removed `cm.is_notification_enabled = TRUE` from the WhatsApp route lookup

- `messages/append_authenticated_dcx_trade_thread_message.py`
  - added logging for notification sent/skipped/failure results after a trade-thread message commit

## Smoke test

1. Set recipient settings to WhatsApp for trade chat notifications.
2. Send a web-app message from the other trader in an existing trade thread.
3. Confirm the message appears in web app.
4. Confirm WhatsApp notification arrives.
5. Confirm Render logs include `trade_thread_message_notification_result`.
