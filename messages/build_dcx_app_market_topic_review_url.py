"""
CONTEXT:
This file builds the canonical authenticated DCX app URL for one market topic.
It exists so inbound email and WhatsApp workflow-outcome replies can point traders back to the
same topic surface without duplicating host/path logic across notification code.
"""

from __future__ import annotations

from users.account_phone.dcx_whatsapp_phone_link_challenge_support import read_dcx_app_base_url


def build_dcx_app_market_topic_review_url(market_topic_id: int) -> str:
    """
    CONTRACT:
      preconditions:
        - market_topic_id identifies one persisted market topic row.
        - The app base URL can be derived from DCX_APP_BASE_URL or the runtime environment.
      postconditions:
        - Returns one authenticated app URL targeting the clean per-topic route.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Slice 1 can now reply to email and WhatsApp market-topic messages with a direct app link.
      WHEN TO USE it:
        - Use it when building trader-facing workflow outcome messages for market topics.
      WHEN NOT TO USE it:
        - Do not use it for public unauthenticated links or admin-only navigation.
      WHAT CAN GO WRONG:
        - A bad app-base-url configuration could point the trader at the wrong host.
      WHAT COMES NEXT:
        - Later signed deep links can be added when DCX supports unauthenticated handoff.

    TESTS:
      - none yet

    ERRORS:
      - API_DCX_MARKET_TOPIC_REVIEW_URL_INVALID_TOPIC_ID:
          suggested_action: Retry with one persisted positive market topic id.
          common_causes:
            - missing market topic id
            - zero or negative id
          recovery_steps:
            - Confirm the market topic row was created.
            - Retry with that market topic id.
          retry_safe: true

    CODE:
    """
    if not isinstance(market_topic_id, int) or market_topic_id <= 0:
        raise RuntimeError("API_DCX_MARKET_TOPIC_REVIEW_URL_INVALID_TOPIC_ID")

    return f"{read_dcx_app_base_url().rstrip('/')}/ai/chats/{market_topic_id}"
