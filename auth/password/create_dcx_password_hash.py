"""
CONTEXT:
This file creates one durable DCX password hash using Argon2id.
It exists so the MVP auth system can store passwords with a modern memory-hard hash instead of
putting raw or weakly derived credentials into the database.
"""

from __future__ import annotations

from argon2 import PasswordHasher


def create_dcx_password_hash(candidate_password: str) -> str:
    """
    CONTRACT:
      preconditions:
        - candidate_password is one non-empty plaintext password string.
      postconditions:
        - Returns one Argon2id password hash string suitable for durable storage.
      side_effects: []
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first DCX password login flow needs one canonical hashing primitive.
      WHEN TO USE it:
        - Use it when a password is first set or reset.
      WHEN NOT TO USE it:
        - Do not use it for session tokens or OTP codes.
      WHAT CAN GO WRONG:
        - An empty or absurdly short password can still be hashed unless validation happens first.
        - The argon2 dependency can be missing from the runtime.
      WHAT COMES NEXT:
        - Password-setup and password-reset capabilities can both depend on this hash path.

    TESTS:
      - password_hash_roundtrip_verifies_successfully

    ERRORS:
      - API_DCX_PASSWORD_HASH_CREATE_FAILED:
          suggested_action: Confirm the argon2 dependency is installed and the candidate password passed validation first.
          common_causes:
            - missing argon2 package
            - invalid runtime environment
          recovery_steps:
            - Install backend requirements.
            - Retry after restoring the auth runtime.
          retry_safe: true

    CODE:
    """
    try:
        return PasswordHasher().hash(candidate_password)
    except Exception as exc:  # pragma: no cover - dependency/runtime path
        raise RuntimeError("API_DCX_PASSWORD_HASH_CREATE_FAILED") from exc
