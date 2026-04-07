"""
CONTEXT:
This file accepts one forgotten-password email and prepares the matching DCX password-reset email challenge.
It exists so the browser-facing reset-request route can stay enumeration-safe while still reusing the
managed challenge and email infrastructure for eligible confirmed users.
"""

from __future__ import annotations

from typing import Any, Callable

from auth.password.create_or_refresh_dcx_password_link_challenge import (
    create_or_refresh_dcx_password_link_challenge,
)
from auth.password.dcx_password_link_challenge_support import (
    DCX_PASSWORD_RESET_CHALLENGE_PURPOSE,
)
from auth.password.read_confirmed_dcx_user_identity_for_password_link_by_email import (
    read_confirmed_dcx_user_identity_for_password_link_by_email,
)
from emails.transactional.build_dcx_password_reset_email_delivery_draft import (
    build_dcx_password_reset_email_delivery_draft,
)


def request_dcx_password_reset_email_challenge(
    email: str,
    connect_to_database: Callable[..., Any] | None = None,
    password_reset_email_delivery_draft_builder: Callable[..., dict] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email is one browser-submitted login email candidate.
      postconditions:
        - Returns one generic accepted payload regardless of whether the email matches an eligible account.
        - For eligible confirmed users, creates or refreshes one password-reset challenge and returns the rendered email draft for later send.
      side_effects:
        - may write to stephen_dcx_user_auth_challenges
      idempotent: false
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Forgot-password should not leak whether a given email exists, but it still needs to prepare the reset email when the account is real.
      WHEN TO USE it:
        - Use it from the password-reset request route behind a coarse route-level rate limit.
      WHEN NOT TO USE it:
        - Do not use it for signup OTP or authenticated password changes.
      WHAT CAN GO WRONG:
        - Unknown or unconfirmed emails should simply produce no email draft.
        - Database or template failures can still happen for real users.
      WHAT COMES NEXT:
        - The route can attempt delivery when a draft is present and still answer the browser with one generic success wrapper.

    TESTS:
      - returns_generic_acceptance_without_email_draft_for_unknown_user
      - returns_password_reset_email_draft_for_confirmed_user

    ERRORS:
      - API_DCX_PASSWORD_LINK_USER_READ_FAILED:
          suggested_action: Confirm backend/database health and retry once the service is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true

    CODE:
    """
    normalized_email = email.strip().lower() if isinstance(email, str) else ""
    build_password_reset_email_delivery_draft = (
        password_reset_email_delivery_draft_builder
        or build_dcx_password_reset_email_delivery_draft
    )

    password_link_target = read_confirmed_dcx_user_identity_for_password_link_by_email(
        normalized_email=normalized_email,
        connect_to_database=connect_to_database,
    )

    if password_link_target is None:
        return {
            "status": "accepted",
            "email_delivery_draft": None,
            "password_set_url": None,
        }

    password_link_payload = create_or_refresh_dcx_password_link_challenge(
        authenticated_user_id=password_link_target["user_id"],
        authenticated_user_identity_id=password_link_target["user_auth_identity_id"],
        challenge_purpose=DCX_PASSWORD_RESET_CHALLENGE_PURPOSE,
        delivery_target_email=password_link_target["primary_email"],
        connect_to_database=connect_to_database,
    )
    email_delivery_draft = build_password_reset_email_delivery_draft(
        language_code=password_link_target["language_code"],
        normalized_email=password_link_target["primary_email"],
        password_set_url=password_link_payload["password_set_url"],
        connect_to_database=connect_to_database,
    )

    return {
        "status": "accepted",
        "email_delivery_draft": email_delivery_draft,
        "password_set_url": password_link_payload["password_set_url"],
    }
