# 2026-05-01 Trade Threads Web Chat Mini Slice

Implemented the first MVP backend for private trader-to-trader conversations about trades.

Added:
- `messages/read_authenticated_dcx_trade_threads_catalog.py`
- `messages/read_authenticated_dcx_trade_thread_detail.py`
- `messages/append_authenticated_dcx_trade_thread_message.py`
- `routes/users/dcx_api_routes_users_me_trade_threads.py`
- Router registration in `dcx_api_app.py`

Behavior:
- `GET /users/me/trade-threads` returns only threads where the authenticated user is owner or counterparty.
- `GET /users/me/trade-threads/{trade_thread_id}` returns one participant-protected thread with ordered messages.
- `POST /users/me/trade-threads/{trade_thread_id}/messages` appends a plain app-surface message if the thread is open and the user is a participant.
- The append capability locks the thread row with `FOR UPDATE` and updates `updated_at_ts_ms`.

Intentional MVP limits:
- Web app only.
- No WhatsApp/email reply routing yet.
- No idempotency key on app composer sends yet, so duplicate clicks are prevented in the UI but not deduplicated at the database layer.
- No translation relay yet; canonical message text equals raw app text.

Verification:
- `python -m py_compile dcx_api_app.py messages/read_authenticated_dcx_trade_threads_catalog.py messages/read_authenticated_dcx_trade_thread_detail.py messages/append_authenticated_dcx_trade_thread_message.py routes/users/dcx_api_routes_users_me_trade_threads.py`
