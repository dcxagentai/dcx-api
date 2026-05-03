CONTEXT:
Implemented the MVP mini slice that lets traders continue private market-topic AI chats from
email or WhatsApp using `#T{id}` references, mirroring the `#C{id}` private trade-chat rule.

CHANGES:
- Added `messages/dcx_inbound_cross_surface_reference_text.py` as the shared text helper for
  extracting reference codes and stripping email reply/header noise.
- Updated the existing private trade-thread router to use the shared helper and require verified
  source contact metadata before routing cross-surface replies.
- Added `messages/route_dcx_inbound_contact_message_to_market_topic_if_applicable.py`.
  It detects `#T` references, verifies the topic is open and owned by the resolved verified user,
  appends a user+assistant AI turn pair, marks the contact message as routed, and sends the AI
  response back on the same email/WhatsApp channel.
- Added `messages/send_dcx_market_topic_ai_turn_response_notification.py` for same-channel AI
  response delivery.
- Extended `messages/append_authenticated_dcx_user_market_topic_ai_chat_turn.py` with optional
  source message/channel/contact/reference metadata and source-message dedupe for webhook retries.
- Wired the new `#T` router into `messages/ingest_dcx_contact_message_from_inbound_envelope.py`
  after `#C` trade routing and before normal classification.
- Updated topic creation outcome notifications in
  `messages/process_stored_dcx_contact_message_analysis.py` to include `#T{id}` and reply
  instructions.
- Follow-up polish: initial email/WhatsApp topic creation notifications now also include the
  opening AI response, so the external channel shows the start of the conversation rather than
  only the topic handle.

VERIFICATION:
- `.\.venv\Scripts\python.exe -m pytest messages\route_dcx_inbound_contact_message_to_trade_thread_if_applicable_test.py messages\route_dcx_inbound_contact_message_to_market_topic_if_applicable_test.py messages\process_stored_dcx_contact_message_analysis_test.py`
- `.\.venv\Scripts\python.exe -m compileall messages\dcx_inbound_cross_surface_reference_text.py messages\route_dcx_inbound_contact_message_to_trade_thread_if_applicable.py messages\route_dcx_inbound_contact_message_to_market_topic_if_applicable.py messages\append_authenticated_dcx_user_market_topic_ai_chat_turn.py messages\send_dcx_market_topic_ai_turn_response_notification.py messages\process_stored_dcx_contact_message_analysis.py messages\ingest_dcx_contact_message_from_inbound_envelope.py`
- `.\.venv\Scripts\python.exe -m pytest messages\process_stored_dcx_contact_message_analysis_test.py messages\route_dcx_inbound_contact_message_to_market_topic_if_applicable_test.py`
- `.\.venv\Scripts\python.exe -m compileall messages\process_stored_dcx_contact_message_analysis.py`

NOTES:
- This remains webhook-inline for the MVP mini slice. A jobs queue should later own AI generation
  and provider response delivery to handle LLM/provider lag with stronger retries.
