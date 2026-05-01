CONTEXT:
Implemented the first MVP mini-slice for private trader-to-AI chats on existing market topics.

WHAT CHANGED:
- Added Gemini boundary `apis/gemini/generate_dcx_gemini_market_topic_chat_response.py`.
- Added app capability `messages/append_authenticated_dcx_user_market_topic_ai_chat_turn.py`.
- Added POST route `/users/me/market-topics/{market_topic_id}/turns` in `routes/users/dcx_api_routes_users_me_market_topic_detail.py`.
- Reused `stephen_dcx_market_topic_turns`; no schema changes were required.

PRODUCT BEHAVIOR:
- A user can open My > Topics, select a topic, see the existing user/assistant turns, type a follow-up, and receive one Gemini response.
- Both the user turn and assistant turn are stored in the same topic turn log.
- The prompt sends the topic title/summary/scope/tags plus all previous turns and the new message.
- MVP context limit is enforced by character budget. When exceeded, the route returns a 409 and the UI stops allowing more messages for that topic chat.

VERIFICATION:
- Backend py_compile passed for the new/changed Python files.
- Frontend TypeScript passed.
- Full `npm run build` passed outside the sandbox; the app still emits the existing large bundle warning.

KNOWN LIMITS:
- No auto-compaction yet.
- No separate AI provider registry yet.
- No cross-channel topic chat routing yet; this mini-slice is app-surface only.
- No dedicated unit tests yet; smoke test through the app route.

