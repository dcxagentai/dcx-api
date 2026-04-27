"""
CONTEXT:
This file sends one email via Resend.
"""

from __future__ import annotations

import html
import os
from typing import Any, Callable


DCX_RESEND_SENDER_PROFILE_TRANSACTIONAL = "transactional"
DCX_RESEND_SENDER_PROFILE_MESSAGES = "messages"


def _read_first_non_empty_env_value(*env_var_names: str) -> str:
    for env_var_name in env_var_names:
        env_var_value = os.getenv(env_var_name, "").strip()
        if env_var_value != "":
            return env_var_value

    return ""


def send_email_via_resend(
    email_delivery_draft: dict,
    sender_profile: str = DCX_RESEND_SENDER_PROFILE_TRANSACTIONAL,
    send_email_with_provider: Callable[[dict], Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_delivery_draft contains non-empty recipient_email, subject, and text_body values.
        - html_body is optional and, when present, contains one pre-rendered safe HTML body.
        - RESEND_API_KEY is configured in the backend environment.
        - RESEND_FROM_NAME is configured in the backend environment.
        - One configured Resend sender email exists for the selected sender profile.
      postconditions:
        - Sends one email through Resend using the configured sender settings.
        - Returns one provider delivery summary with provider_message_id when available.
      side_effects:
        - sends one email through the configured Resend account
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - DCX domain email flows should not need to know about Resend SDK details or sender env vars.
      WHEN TO USE it:
        - Use it from provider-agnostic transactional email functions that currently default to Resend.
      WHEN NOT TO USE it:
        - Do not use it for browser-facing responses.
        - Do not use it when a domain flow should remain provider-free in tests and can inject a fake sender.
      WHAT CAN GO WRONG:
        - Missing Resend config, malformed email draft content, invalid sender config, or provider failures can all reject the send.
      WHAT COMES NEXT:
        - Other providers can later implement the same shape behind parallel adapter folders.
        - The selected sender profile lets DCX keep transactional mail separate from conversational message traffic.

    TESTS:
      - resend_adapter_builds_test_mode_params_with_explicit_sender_and_override_recipient
      - resend_adapter_returns_provider_message_id_when_provider_accepts_send
      - resend_adapter_raises_clear_error_when_required_config_missing
      - resend_adapter_raises_clear_error_when_required_draft_fields_are_missing

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:
          suggested_action: Configure the required Resend environment values before attempting email delivery.
          common_causes:
            - missing RESEND_API_KEY
            - missing RESEND_FROM_NAME
            - missing RESEND_FROM_EMAIL_TRANSACTIONAL or RESEND_FROM_EMAIL_MESSAGES for the selected profile
          recovery_steps:
            - Add the missing Resend configuration values.
            - Restart the backend.
            - Retry the request.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_DRAFT_INVALID:
          suggested_action: Rebuild the email draft with recipient_email, subject, and text_body before attempting delivery.
          common_causes:
            - missing recipient_email
            - missing subject
            - missing text_body
            - blank draft field values
          recovery_steps:
            - Inspect the email draft builder output.
            - Restore the missing draft fields.
            - Retry the send once the draft is complete.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED:
          suggested_action: Check provider configuration and retry later.
          common_causes:
            - invalid sender configuration
            - provider outage
          recovery_steps:
            - Verify the sender settings.
            - Retry after the provider is healthy.
          retry_safe: false
          what_changed:
            - unknown whether Resend accepted, rejected, or partially processed the outbound request
          rollback_needed: false
          rollback_operation:
            - none in the provider adapter; inspect provider logs or retry through the owning flow when appropriate
      - API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN:
          suggested_action: Remove the test-recipient override or explicitly enable it for local testing only.
          common_causes:
            - test recipient override left configured in a non-local environment
          recovery_steps:
            - Remove RESEND_TEST_RECIPIENT.
            - Or set RESEND_ALLOW_TEST_RECIPIENT_OVERRIDE=true in a local-only environment.
          retry_safe: true

    CODE:
    """
    if sender_profile not in {
        DCX_RESEND_SENDER_PROFILE_TRANSACTIONAL,
        DCX_RESEND_SENDER_PROFILE_MESSAGES,
    }:
        raise RuntimeError("API_DCX_RESEND_SENDER_PROFILE_INVALID")

    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    sender_name = os.getenv("RESEND_FROM_NAME", "").strip()
    sender_email = _read_dcx_resend_sender_email_for_profile(sender_profile)
    missing_config_vars: list[str] = []

    if resend_api_key == "":
        missing_config_vars.append("RESEND_API_KEY")

    if sender_name == "":
        missing_config_vars.append("RESEND_FROM_NAME")

    if sender_email == "":
        missing_config_vars.append(
            "RESEND_FROM_EMAIL_MESSAGES"
            if sender_profile == DCX_RESEND_SENDER_PROFILE_MESSAGES
            else "RESEND_FROM_EMAIL_TRANSACTIONAL"
        )

    if len(missing_config_vars) > 0:
        raise RuntimeError(
            "API_PUBLIC_EMAIL_SIGNUP_RESEND_CONFIGURATION_MISSING:"
            + ",".join(missing_config_vars)
        )

    missing_draft_fields: list[str] = []

    for required_draft_field in ["recipient_email", "subject", "text_body"]:
        draft_value = email_delivery_draft.get(required_draft_field)
        if not isinstance(draft_value, str) or draft_value.strip() == "":
            missing_draft_fields.append(required_draft_field)

    if len(missing_draft_fields) > 0:
        raise RuntimeError(
            "API_PUBLIC_EMAIL_SIGNUP_RESEND_DRAFT_INVALID:"
            + ",".join(missing_draft_fields)
        )

    test_recipient_override = (
        _read_first_non_empty_env_value("RESEND_TEST_RECIPIENT")
        or None
    )
    runtime_environment = os.getenv("DCX_ENVIRONMENT", "").strip().lower()
    allow_test_recipient_override = _read_first_non_empty_env_value("RESEND_ALLOW_TEST_RECIPIENT_OVERRIDE").lower()

    if test_recipient_override is not None and (
        runtime_environment not in {"local", "development"}
        or allow_test_recipient_override != "true"
    ):
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_TEST_RECIPIENT_OVERRIDE_FORBIDDEN")

    actual_recipient_email = test_recipient_override or email_delivery_draft["recipient_email"]
    resend_send_params = {
        "from": f"{sender_name} <{sender_email}>",
        "to": [actual_recipient_email],
        "subject": email_delivery_draft["subject"],
        "text": email_delivery_draft["text_body"],
        "html": email_delivery_draft.get("html_body")
        or "<div>" + html.escape(email_delivery_draft["text_body"]).replace("\n", "<br />") + "</div>",
    }

    try:
        import resend

        resend.api_key = resend_api_key
        send_email = send_email_with_provider or resend.Emails.send
        response = send_email(resend_send_params)
    except Exception as exc:
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED") from exc

    if isinstance(response, dict):
        message_id = response.get("id")
    else:
        message_id = getattr(response, "id", None)

    return {
        "provider": "resend",
        "status": "accepted",
        "provider_message_id": message_id,
    }


def _read_dcx_resend_sender_email_for_profile(sender_profile: str) -> str:
    if sender_profile == DCX_RESEND_SENDER_PROFILE_MESSAGES:
        return os.getenv("RESEND_FROM_EMAIL_MESSAGES", "").strip()

    return os.getenv("RESEND_FROM_EMAIL_TRANSACTIONAL", "").strip()
