"""
CONTEXT:
This file appends DCX email-preference management links to one rendered newsletter email body pair.
It exists so outbound newsletter emails carry one-click unsubscribe links that match the new
preference and suppression model.
"""

from __future__ import annotations

from users.account.dcx_email_preference_unsubscribe_support import (
    DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_ALL,
    DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_NEWSLETTERS,
    DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_PROMOTIONAL,
    build_dcx_email_preference_unsubscribe_token,
    build_dcx_email_preference_unsubscribe_url,
)


def append_dcx_email_preferences_footer_to_newsletter_email_bodies(
    rendered_bodies: dict[str, str],
    user_id: int,
    recipient_email: str,
    current_timestamp_ms_provider=None,
) -> dict[str, str]:
    """
    CONTRACT:
      preconditions:
        - rendered_bodies contains `text_body` and `html_body`.
        - user_id and recipient_email identify the outbound recipient.
      postconditions:
        - Returns one updated body pair with three unsubscribe links and one transactional-email note appended.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Newsletter sends should carry preference-management links directly in the email body.
      WHEN TO USE it:
        - Use it after markdown rendering and before provider delivery for newsletter emails.
      WHEN NOT TO USE it:
        - Do not use it for transactional account or security emails.
      WHAT CAN GO WRONG:
        - Missing unsubscribe secret configuration would prevent link generation.
      WHAT COMES NEXT:
        - Sequence and campaign sends can reuse the same footer approach once their delivery path is active.

    TESTS:
      - appends_three_unsubscribe_links_to_rendered_bodies

    ERRORS:
      - API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_INVALID:
          suggested_action: Configure the unsubscribe secret and rebuild the outbound email.
          common_causes:
            - missing auth challenge secret
            - missing signup OTP fallback secret
          recovery_steps:
            - Set the required secret.
            - Retry the send.
          retry_safe: true

    CODE:
    """
    unsubscribe_all_url = _build_unsubscribe_url(
        user_id=user_id,
        recipient_email=recipient_email,
        unsubscribe_kind=DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_ALL,
        current_timestamp_ms_provider=current_timestamp_ms_provider,
    )
    unsubscribe_promotional_url = _build_unsubscribe_url(
        user_id=user_id,
        recipient_email=recipient_email,
        unsubscribe_kind=DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_PROMOTIONAL,
        current_timestamp_ms_provider=current_timestamp_ms_provider,
    )
    unsubscribe_newsletters_url = _build_unsubscribe_url(
        user_id=user_id,
        recipient_email=recipient_email,
        unsubscribe_kind=DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_NEWSLETTERS,
        current_timestamp_ms_provider=current_timestamp_ms_provider,
    )

    text_footer = (
        "\n\n---\n"
        "Email preferences\n"
        f"Unsubscribe from all email: {unsubscribe_all_url}\n"
        f"Unsubscribe from promotional email: {unsubscribe_promotional_url}\n"
        f"Unsubscribe from newsletters: {unsubscribe_newsletters_url}\n\n"
        "Transactional account and security emails will still be sent when needed."
    )
    html_footer = (
        "<hr />"
        "<p><strong>Email preferences</strong></p>"
        f"<p><a href=\"{unsubscribe_all_url}\" target=\"_blank\" rel=\"noreferrer\">Unsubscribe from all email</a><br />"
        f"<a href=\"{unsubscribe_promotional_url}\" target=\"_blank\" rel=\"noreferrer\">Unsubscribe from promotional email</a><br />"
        f"<a href=\"{unsubscribe_newsletters_url}\" target=\"_blank\" rel=\"noreferrer\">Unsubscribe from newsletters</a></p>"
        "<p>Transactional account and security emails will still be sent when needed.</p>"
    )

    return {
        "text_body": (rendered_bodies["text_body"] or "") + text_footer,
        "html_body": (rendered_bodies["html_body"] or "<div></div>").replace("</div>", html_footer + "</div>", 1),
    }


def _build_unsubscribe_url(
    user_id: int,
    recipient_email: str,
    unsubscribe_kind: str,
    current_timestamp_ms_provider=None,
) -> str:
    raw_token = build_dcx_email_preference_unsubscribe_token(
        user_id=user_id,
        recipient_email=recipient_email,
        unsubscribe_kind=unsubscribe_kind,
        current_timestamp_ms_provider=current_timestamp_ms_provider,
    )
    return build_dcx_email_preference_unsubscribe_url(unsubscribe_kind, raw_token)
