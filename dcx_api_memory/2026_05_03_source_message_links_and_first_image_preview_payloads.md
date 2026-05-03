CONTEXT:
Added source-message provenance payloads for topic, trade, and trade-chat detail screens.

CHANGES:
- Added `messages/read_authenticated_dcx_source_message_first_image_attachment.py`.
- Topic detail payloads now include `source_first_image_attachment`.
- Trade detail payloads now include `source_first_image_attachment`.
- Trade-thread detail payloads now include `source_message_id` and `source_first_image_attachment`.

NOTES:
- Image descriptors use the existing private attachment route:
  `/users/me/messages/{message_id}/attachments/{attachment_id}/file`.
- That route currently enforces message ownership, so source image previews are safest for owner
  views. If counterparties should see source images in trade chats, the attachment stream boundary
  should get an explicit trade-thread participant authorization path.

VERIFICATION:
- `.\.venv\Scripts\python.exe -m compileall messages\read_authenticated_dcx_source_message_first_image_attachment.py messages\read_authenticated_dcx_user_market_topic_detail.py messages\read_authenticated_dcx_user_trade_detail.py messages\read_authenticated_dcx_trade_thread_detail.py`
