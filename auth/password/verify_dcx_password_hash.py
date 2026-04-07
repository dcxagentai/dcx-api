"""
CONTEXT:
This file verifies one plaintext password against one stored DCX password hash.
It exists so login can use the same canonical Argon2id verification path every time.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


def verify_dcx_password_hash(candidate_password: str, stored_password_hash: str) -> bool:
    """
    CONTRACT:
      preconditions:
        - candidate_password is the submitted plaintext password.
        - stored_password_hash is one previously stored Argon2id hash.
      postconditions:
        - Returns true when the candidate matches the stored hash.
        - Returns false when the candidate does not match or the hash is invalid.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Login should have one clear verification primitive instead of ad hoc comparisons.
      WHEN TO USE it:
        - Use it when authenticating an email/password login attempt.
      WHEN NOT TO USE it:
        - Do not use it for OTP codes or session tokens.
      WHAT CAN GO WRONG:
        - The stored hash can be malformed.
        - The argon2 dependency can be missing from the runtime.
      WHAT COMES NEXT:
        - Login can decide whether to return a generic invalid-credentials error.

    TESTS:
      - password_hash_roundtrip_verifies_successfully
      - verify_returns_false_for_wrong_password

    ERRORS:
      - API_DCX_PASSWORD_HASH_VERIFY_FAILED:
          suggested_action: Confirm the argon2 dependency is installed and the stored hash format is valid.
          common_causes:
            - missing argon2 package
            - corrupt stored password hash
          recovery_steps:
            - Install backend requirements.
            - Repair the stored credential row if the hash is corrupt.
          retry_safe: true

    CODE:
    """
    try:
        return PasswordHasher().verify(stored_password_hash, candidate_password)
    except (VerificationError, InvalidHashError):
        return False
    except Exception as exc:  # pragma: no cover - dependency/runtime path
        raise RuntimeError("API_DCX_PASSWORD_HASH_VERIFY_FAILED") from exc
