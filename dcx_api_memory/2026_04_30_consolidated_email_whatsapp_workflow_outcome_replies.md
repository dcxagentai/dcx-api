CONTEXT:
Slice 1 now replies to email and WhatsApp inputs with one consolidated workflow outcome message after
classification and projection completes.

WHAT CHANGED:
- Replaced the per-trade notification loop in `messages/process_stored_dcx_contact_message_analysis.py`
  with a message-level workflow outcome payload.
- Email and WhatsApp-originated messages now receive one reply per input message.
- Mixed messages list all created trade candidates and market topics in that single reply.
- Trade-only messages list all trade candidates with clean `/me/trades/{id}` links.
- Topic-only messages list all topics with clean `/me/topics/{id}` links.
- Other messages receive a saved/no-trade-or-topic outcome.
- Prohibited messages receive a blocked-by-policy outcome and no workflow links.
- App-originated messages do not receive provider replies because the app already shows the send trail and links.

FILES:
- `messages/process_stored_dcx_contact_message_analysis.py`
- `messages/process_stored_dcx_contact_message_analysis_test.py`
- `messages/build_dcx_app_market_topic_review_url.py`
- `apis/meta_whatsapp/send_dcx_whatsapp_message_workflow_outcome_notification.py`
- `apis/meta_whatsapp/send_dcx_whatsapp_message_workflow_outcome_notification_test.py`
- `emails/transactional/send_dcx_email_message_workflow_outcome_notification.py`
- `emails/transactional/send_dcx_email_message_workflow_outcome_notification_test.py`

VERIFICATION:
- `.\.venv\Scripts\python.exe -m pytest messages\process_stored_dcx_contact_message_analysis_test.py apis\meta_whatsapp\send_dcx_whatsapp_message_workflow_outcome_notification_test.py emails\transactional\send_dcx_email_message_workflow_outcome_notification_test.py -q`
  - 7 passed
- `.\.venv\Scripts\python.exe -m py_compile messages\process_stored_dcx_contact_message_analysis.py apis\meta_whatsapp\send_dcx_whatsapp_message_workflow_outcome_notification.py emails\transactional\send_dcx_email_message_workflow_outcome_notification.py messages\build_dcx_app_market_topic_review_url.py`
  - passed
- `.\.venv\Scripts\python.exe -m pytest messages\process_stored_dcx_contact_message_analysis_test.py apis\meta_whatsapp\send_dcx_whatsapp_message_workflow_outcome_notification_test.py emails\transactional\send_dcx_email_message_workflow_outcome_notification_test.py messages\process_dcx_meta_whatsapp_inbound_webhook_payload_test.py apis\meta_whatsapp\mark_dcx_meta_whatsapp_inbound_message_as_read_test.py apis\meta_whatsapp\read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload_test.py routes\public\dcx_api_routes_public_meta_whatsapp_webhooks_test.py -q`
  - 19 passed

NOTES:
- The old trade-version metadata keys are still written for trade candidates so existing UI text such as
  notification status can continue to work.
- This intentionally does not add provider-level deduplication yet. The message-analysis job claim still
  prevents ordinary duplicate sends; richer outbound notification records can be added when Slice 2 brings
  reply parsing and conversation state.
