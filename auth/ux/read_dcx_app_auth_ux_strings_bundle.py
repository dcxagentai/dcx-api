"""
CONTEXT:
This file reads the localized UX-string bundle for the DCX app auth pages.
It exists so unauthenticated app routes such as login, forgot-password, and password set/reset
can participate in the same multilingual UX-string system as the rest of DCX.
"""

from __future__ import annotations

from typing import Any, Callable

from languages.read_live_dcx_ux_string_group_with_language_fallback import (
    read_live_dcx_ux_string_group_with_language_fallback_capability,
)

DCX_APP_AUTH_DEFAULT_LANGUAGE_CODE = "en"

DCX_APP_AUTH_COMMON_DEFAULT_UX_STRINGS = {
    "checking_session": "Checking DCX session...",
}

DCX_APP_AUTH_LOGIN_PAGE_DEFAULT_UX_STRINGS = {
    "surface_label": "DCX App",
    "page_title": "Sign in",
    "hero_eyebrow": "Account access",
    "hero_title": "Continue into the private DCX app.",
    "hero_body": "Use the same shared DCX session for both the app and internal admin surfaces.",
    "auth_eyebrow": "Shared auth",
    "auth_title": "Email and password",
    "auth_body": "Confirmed users with a password can enter the app immediately. Admin access stays role-gated on top of the same browser session.",
    "field_email": "Email",
    "field_email_placeholder": "you@company.com",
    "field_password": "Password",
    "field_password_placeholder": "Enter your password",
    "help_idle": "Use your confirmed email and current password. If you lost access, request a new password link.",
    "submit_idle": "Sign in",
    "submit_pending": "Signing in...",
    "forgot_password_button": "Forgot password?",
}

DCX_APP_AUTH_PASSWORD_RESET_REQUEST_PAGE_DEFAULT_UX_STRINGS = {
    "surface_label": "DCX App",
    "page_title": "Reset password",
    "hero_eyebrow": "Recovery",
    "hero_title": "Send a secure password link to your confirmed email.",
    "hero_body": "If the account exists and is already confirmed, DCX will send a one-time password link to the email address you enter here.",
    "auth_eyebrow": "Shared auth",
    "auth_title": "Password reset email",
    "auth_body": "The response stays generic for security. Use the newest email link only once.",
    "field_email": "Email",
    "field_email_placeholder": "you@company.com",
    "help_idle": "We will send a one-time link to the confirmed account email if it exists.",
    "success_message": "If that email belongs to a confirmed DCX account, a secure password link is on the way.",
    "submit_idle": "Send password link",
    "submit_pending": "Sending...",
    "back_to_login_button": "Back to sign in",
}

DCX_APP_AUTH_PASSWORD_SET_PAGE_DEFAULT_UX_STRINGS = {
    "surface_label": "DCX App",
    "page_title": "Password",
    "hero_eyebrow": "Shared auth",
    "hero_title_setup": "Create your DCX password.",
    "hero_body_setup": "Your email is now verified. Choose the password you will use to enter the private DCX app.",
    "hero_title_reset": "Choose a new password.",
    "hero_body_reset": "Use the secure link token from your reset email to choose a new password, then sign in again.",
    "rule_eyebrow": "Password rule",
    "rule_title": "At least 12 characters",
    "rule_body": "Longer passphrases are welcome. Once saved, return to sign in with the new password.",
    "field_password": "New password",
    "field_password_placeholder": "Enter a strong passphrase",
    "field_confirm_password": "Confirm password",
    "field_confirm_password_placeholder": "Enter the same password again",
    "validation_min_length": "Use a password with at least 12 characters.",
    "validation_confirmation_mismatch": "The password confirmation must match exactly.",
    "token_missing_error": "This password link is missing or has already been cleared. Request a fresh one and retry.",
    "help_idle": "This one-time link works only once. If it expires, request another password email.",
    "success_message": "Password saved. Continue back to sign in.",
    "submit_idle": "Save password",
    "submit_pending": "Saving...",
    "back_to_login_button": "Back to sign in",
}


def read_dcx_app_auth_ux_strings_bundle_capability(
    language_code: str | None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - language_code is either null or one requested browser language code such as `en`, `es`, `fr`, or `de`.
      postconditions:
        - Returns one complete localized UX-string bundle for the app auth pages.
        - Falls back to English/original/default values when translations are missing.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The app auth pages remain visible before sign-in, so they cannot rely on the authenticated
          account summary to resolve multilingual UX copy.
      WHEN TO USE it:
        - Use it from the browser-facing auth UX route for app login, reset request, and password set pages.
      WHEN NOT TO USE it:
        - Do not use it for the account page or admin pages.
      WHAT CAN GO WRONG:
        - UX-string groups may not be seeded yet.
        - Requested-language rows may be incomplete during rollout.
      WHAT COMES NEXT:
        - The frontend can reuse the same bundle while moving between login and password-reset steps.

    TESTS:
      - returns_bundle_with_selected_language_rows_when_present
      - falls_back_to_defaults_when_groups_are_missing

    ERRORS:
      - API_DCX_APP_AUTH_UX_STRINGS_READ_FAILED:
          suggested_action: Retry after the backend and database are healthy.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true

    CODE:
    """
    normalized_language_code = (
        language_code.strip().lower()
        if isinstance(language_code, str) and language_code.strip() != ""
        else DCX_APP_AUTH_DEFAULT_LANGUAGE_CODE
    )

    try:
        return {
            "language_code": normalized_language_code,
            "common": read_live_dcx_ux_string_group_with_language_fallback_capability(
                string_group="app_auth_common",
                language_code=normalized_language_code,
                default_ux_strings=DCX_APP_AUTH_COMMON_DEFAULT_UX_STRINGS,
                connect_to_database=connect_to_database,
            ),
            "login_page": read_live_dcx_ux_string_group_with_language_fallback_capability(
                string_group="app_auth_login_page",
                language_code=normalized_language_code,
                default_ux_strings=DCX_APP_AUTH_LOGIN_PAGE_DEFAULT_UX_STRINGS,
                connect_to_database=connect_to_database,
            ),
            "password_reset_request_page": read_live_dcx_ux_string_group_with_language_fallback_capability(
                string_group="app_auth_password_reset_request_page",
                language_code=normalized_language_code,
                default_ux_strings=DCX_APP_AUTH_PASSWORD_RESET_REQUEST_PAGE_DEFAULT_UX_STRINGS,
                connect_to_database=connect_to_database,
            ),
            "password_set_page": read_live_dcx_ux_string_group_with_language_fallback_capability(
                string_group="app_auth_password_set_page",
                language_code=normalized_language_code,
                default_ux_strings=DCX_APP_AUTH_PASSWORD_SET_PAGE_DEFAULT_UX_STRINGS,
                connect_to_database=connect_to_database,
            ),
        }
    except RuntimeError as exc:
        if str(exc) == "API_LIVE_DCX_UX_STRING_GROUP_READ_FAILED":
            raise RuntimeError("API_DCX_APP_AUTH_UX_STRINGS_READ_FAILED") from exc
        raise
