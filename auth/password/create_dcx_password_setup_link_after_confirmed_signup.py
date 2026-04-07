"""
CONTEXT:
This file creates one password-setup handoff URL immediately after DCX signup OTP confirmation.
It exists so the public signup flow can continue straight into password setup on the app domain
without requiring a second email round trip.
"""

from __future__ import annotations

from typing import Any, Callable

from auth.password.create_or_refresh_dcx_password_link_challenge import (
    create_or_refresh_dcx_password_link_challenge,
)
from auth.password.dcx_password_link_challenge_support import (
    DCX_PASSWORD_SETUP_CHALLENGE_PURPOSE,
)
from auth.password.read_confirmed_dcx_user_identity_for_password_link_by_email import (
    read_confirmed_dcx_user_identity_for_password_link_by_email,
)


def create_dcx_password_setup_link_after_confirmed_signup(
    confirmed_email: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - confirmed_email belongs to one user already confirmed by the signup OTP flow.
      postconditions:
        - Returns one password-setup URL when the confirmed user identity can be resolved.
        - Raises a stable error when the confirmed user cannot be re-read for setup.
      side_effects:
        - writes to stephen_dcx_user_auth_challenges
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Successful signup OTP verification should hand the browser directly into password setup on the app surface.
      WHEN TO USE it:
        - Use it immediately after the signup OTP capability confirms the user.
      WHEN NOT TO USE it:
        - Do not use it for ordinary forgotten-password reset.
      WHAT CAN GO WRONG:
        - The confirmed user identity can fail to resolve due to DB issues or unexpected data drift.
      WHAT COMES NEXT:
        - The public OTP route can include the returned URL in its success payload and redirect there.

    TESTS:
      - setup_link_creation_returns_password_setup_url_for_confirmed_user

    ERRORS:
      - API_DCX_PASSWORD_SETUP_TARGET_NOT_FOUND:
          suggested_action: Use the password-reset flow from the login page.
          common_causes:
            - confirmed user identity missing
            - signup completed but identity row drifted
          recovery_steps:
            - Open the app login page.
            - Request a password reset email.
          retry_safe: true

    CODE:
    """
    password_link_target = read_confirmed_dcx_user_identity_for_password_link_by_email(
        normalized_email=confirmed_email.strip().lower(),
        connect_to_database=connect_to_database,
    )

    if password_link_target is None:
        raise RuntimeError("API_DCX_PASSWORD_SETUP_TARGET_NOT_FOUND")

    return create_or_refresh_dcx_password_link_challenge(
        authenticated_user_id=password_link_target["user_id"],
        authenticated_user_identity_id=password_link_target["user_auth_identity_id"],
        challenge_purpose=DCX_PASSWORD_SETUP_CHALLENGE_PURPOSE,
        delivery_target_email=password_link_target["primary_email"],
        connect_to_database=connect_to_database,
    )
