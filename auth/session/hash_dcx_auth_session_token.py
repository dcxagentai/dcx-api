"""
CONTEXT:
This file hashes one raw DCX auth session token before database storage or lookup.
It exists so the backend never needs to store raw bearer session tokens directly.
"""

from __future__ import annotations

import hashlib


def hash_dcx_auth_session_token(raw_session_token: str) -> str:
    """
    CONTRACT:
      preconditions:
        - raw_session_token is one non-empty session token string.
      postconditions:
        - Returns one deterministic SHA-256 hex digest for the session token.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Session tables should store only token hashes, not raw session secrets.
      WHEN TO USE it:
        - Use it before inserting or looking up auth session rows.
      WHEN NOT TO USE it:
        - Do not use it for passwords.
      WHAT CAN GO WRONG:
        - Empty tokens can still hash unless callers validate their inputs.
      WHAT COMES NEXT:
        - Session create/read/revoke capabilities all depend on this shared token-hash shape.

    TESTS:
      - hashes_session_token_deterministically

    ERRORS: []

    CODE:
    """
    return hashlib.sha256(raw_session_token.encode("utf-8")).hexdigest()
