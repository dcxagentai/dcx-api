CONTEXT:
During live cross-surface trade-chat testing, an email reply body included the trader's new text
plus the quoted prior DCX notification. That quoted block then appeared in the WhatsApp
notification sent to the other participant.

CHANGES:
- `messages/route_dcx_inbound_contact_message_to_trade_thread_if_applicable.py` now stops routed
  message text at common email reply quote boundaries such as `Replying to ...` and
  `On ... wrote:`.
- The same router now also stops at quoted email header lines such as `From:`, `To:`, `Date:`,
  and `Subject:` so email addresses and mail-client metadata do not leak into the app timeline
  or onward WhatsApp/email notifications.
- User-authored email subjects are preserved with the cleaned body text for fresh email-origin
  trade-thread messages, while DCX-generated reply subjects such as `Re: DCX trade chat C2` are
  treated as routing noise and dropped.
- Added focused unit coverage in
  `messages/route_dcx_inbound_contact_message_to_trade_thread_if_applicable_test.py`.

VERIFICATION:
- `.\.venv\Scripts\python.exe -m pytest messages\route_dcx_inbound_contact_message_to_trade_thread_if_applicable_test.py`
- `.\.venv\Scripts\python.exe -m compileall messages\route_dcx_inbound_contact_message_to_trade_thread_if_applicable.py`
