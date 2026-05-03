# 2026-05-03 - Market Topic Gemini System Instruction And Role Turns

## Context
We reviewed the new cross-surface market topic chat flow after WhatsApp screenshot-to-topic testing.
The first AI topic response had claimed that DCX was "tracking" or "monitoring" a live situation even
though no monitoring job exists for that topic.

## Decision
- Leave the initial contact-message collation prompt unchanged.
- Keep separate prompts for:
  - market topic seed creation;
  - market topic chat continuation.
- Add one shared Gemini system instruction for both topic seed and topic chat calls.
- Keep product truth guidance compact for now, rather than adding a long list of prohibited phrases.
- Move topic chat continuation from a plain transcript blob to Gemini role-based contents rebuilt from
  persisted database turns.
- Increase the MVP topic chat context guard from 28,000 characters to 100,000 characters.
- Remove `suggested_next_prompts` from the topic seed prompt and response schema because the app does
  not currently render or use those suggestions.

## Implementation
- Added `apis/gemini/build_dcx_gemini_market_topic_system_instruction.py`.
- Updated `apis/gemini/generate_dcx_gemini_structured_market_topic_seed.py` to inject the shared
  `system_instruction`, keep JSON schema output, and drop `suggested_next_prompts`.
- Updated `apis/gemini/generate_dcx_gemini_market_topic_chat_response.py` to send Gemini role-based
  `contents`:
  - topic/task context as a user content item;
  - persisted user turns as `role="user"`;
  - persisted assistant turns as `role="model"`;
  - current trader message as the final `role="user"` content item.
- Updated `messages/append_authenticated_dcx_user_market_topic_ai_chat_turn.py` context limit to 100,000.
- Removed dormant `suggested_next_prompts` topic metadata storage from new projected topics.

## Verification
- Focused backend tests passed: 9 tests.
- Focused Python compileall passed for the changed backend files.

## Notes
`topic_scope_text` is the concise boundary of the topic chat: what this topic is about and what kind of
follow-up analysis belongs inside it. It is not shown prominently in the current UI, but it anchors the
chat context alongside title, summary, and tags.
