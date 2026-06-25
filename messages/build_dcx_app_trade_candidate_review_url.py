"""
CONTEXT:
This file builds the canonical authenticated DCX app review URL for one trade candidate.
It exists so app, WhatsApp, and email trade-confirmation flows can all point traders back to
the same review surface without duplicating host/path logic across message-domain files.
"""

from __future__ import annotations

from users.account_phone.dcx_whatsapp_phone_link_challenge_support import read_dcx_app_base_url


def build_dcx_app_trade_candidate_review_url(trade_id: int) -> str:
    """
    CONTRACT:
      preconditions:
        - trade_id identifies one persisted trade candidate row.
        - The app base URL can be derived from DCX_APP_BASE_URL or the runtime environment.
      postconditions:
        - Returns one authenticated app URL targeting the clean per-trade route.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Slice 1 keeps the app as the canonical trade-confirmation surface even when the source
          message arrived through WhatsApp or email.
      WHEN TO USE it:
        - Use it when building trader-facing confirmation nudges for trade candidates.
      WHEN NOT TO USE it:
        - Do not use it for public unauthenticated links or admin-only navigation.
      WHAT CAN GO WRONG:
        - A bad or missing app-base-url configuration could point the trader at the wrong host.
      WHAT COMES NEXT:
        - Later secure deep-link variants can add signed context tokens when anonymous access is needed.

    TESTS:
      - none yet

    ERRORS:
      - API_DCX_TRADE_REVIEW_URL_INVALID_TRADE_ID:
          suggested_action: Retry with one persisted positive trade id.
          common_causes:
            - missing trade id
            - zero or negative id
          recovery_steps:
            - Confirm the trade row was created.
            - Retry with that trade id.
          retry_safe: true

    CODE:
    """
    if not isinstance(trade_id, int) or trade_id <= 0:
        raise RuntimeError("API_DCX_TRADE_REVIEW_URL_INVALID_TRADE_ID")

    return f"{read_dcx_app_base_url().rstrip('/')}/trades/objects/{trade_id}"
