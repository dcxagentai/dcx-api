"""
CONTEXT:
This file owns the public one-click DCX email unsubscribe boundary.
It exists so recipients can apply email preference changes directly from newsletter or promotional
emails without already being signed into the app.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from users.account.apply_dcx_public_email_unsubscribe_request import (
    apply_dcx_public_email_unsubscribe_request_capability,
)

dcx_api_routes_public_email_preferences_unsubscribe_router = APIRouter(
    prefix="/public/email-preferences",
    tags=["public_email_preferences"],
)


@dcx_api_routes_public_email_preferences_unsubscribe_router.get(
    "/unsubscribe/{unsubscribe_kind}/{raw_unsubscribe_token}",
    response_class=HTMLResponse,
)
def get_dcx_public_email_preferences_unsubscribe_confirmation_page(
    unsubscribe_kind: str,
    raw_unsubscribe_token: str,
) -> HTMLResponse:
    """
    CONTRACT:
      preconditions:
        - unsubscribe_kind and raw_unsubscribe_token come from one signed unsubscribe link in a DCX email.
        - The configured database is reachable.
      postconditions:
        - Applies the unsubscribe request when the token is valid.
        - Returns one minimal human-readable confirmation page.
        - Returns one minimal human-readable error page when the token is invalid, expired, or stale.
      side_effects:
        - updates one user preference and/or one newsletter suppression row
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: public_email_unsubscribe_route:{unsubscribe_kind}:{raw_unsubscribe_token}
      locks: []
      contention_strategy: delegates write coordination to the unsubscribe capability

    NARRATIVE:
      WHY this exists:
        - Email recipients should not need to sign in just to stop newsletters or promotional mail.
      WHEN TO USE it:
        - Use it only for one-click unsubscribe links emitted in DCX outbound email footers.
      WHEN NOT TO USE it:
        - Do not use it as a generic account-management page.
      WHAT CAN GO WRONG:
        - The link can be stale, expired, or malformed.
        - The database can be unavailable.
      WHAT COMES NEXT:
        - The app account settings page remains the signed-in place for opting back in and managing preferences more explicitly.

    TESTS:
      - public_unsubscribe_route_returns_confirmation_page_for_valid_request
      - public_unsubscribe_route_returns_error_page_for_invalid_request

    ERRORS:
      - API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_INVALID:
          suggested_action: Retry from the full unsubscribe link in the newest email.
          common_causes:
            - malformed or tampered link
          recovery_steps:
            - Reopen the email.
            - Retry with the full link.
          retry_safe: true

    CODE:
    """
    try:
        payload = apply_dcx_public_email_unsubscribe_request_capability(
            unsubscribe_kind=unsubscribe_kind,
            raw_unsubscribe_token=raw_unsubscribe_token,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = 410 if error_code == "API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_EXPIRED" else 404 if error_code == "API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_NOT_FOUND" else 400
        return HTMLResponse(
            status_code=status_code,
            content=_build_dcx_public_email_unsubscribe_error_page_html(error_code),
        )

    return HTMLResponse(
        status_code=200,
        content=_build_dcx_public_email_unsubscribe_confirmation_page_html(payload),
    )


def _build_dcx_public_email_unsubscribe_confirmation_page_html(payload: dict) -> str:
    message_by_kind = {
        "all": "You will no longer receive newsletters, campaigns, or promotional sequences. Transactional account and security emails can still be sent when needed.",
        "promotional": "You will no longer receive campaigns or promotional sequences. Newsletter delivery remains available unless you unsubscribe from newsletters separately.",
        "newsletters": "Your newsletter preference has been updated. Transactional account emails stay available, and promotional email behavior remains separate.",
    }
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>DCX Email Preferences Updated</title>
  </head>
  <body style="font-family: Georgia, serif; margin: 2rem; color: #1f2937;">
    <main style="max-width: 42rem;">
      <p style="font-size: 0.8rem; letter-spacing: 0.16em; text-transform: uppercase; color: #64748b;">DCX Email Preferences</p>
      <h1 style="margin-bottom: 0.75rem;">Preference updated</h1>
      <p>{message_by_kind.get(payload["unsubscribe_kind"], "Your email preferences were updated.")}</p>
      <p style="color: #475569;">You can change these settings later from your signed-in DCX account.</p>
    </main>
  </body>
</html>"""


def _build_dcx_public_email_unsubscribe_error_page_html(error_code: str) -> str:
    if error_code == "API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_EXPIRED":
        heading = "This unsubscribe link has expired"
        message = "Use a newer email or update your preferences from the signed-in DCX account page."
    elif error_code == "API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_NOT_FOUND":
        heading = "We could not match this unsubscribe request"
        message = "The email address or account tied to this link no longer matches. Try a newer email or sign in to adjust preferences directly."
    else:
        heading = "We could not update your email preferences"
        message = "Please retry from the full unsubscribe link in the email, or update preferences from your signed-in DCX account."

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>DCX Email Preferences</title>
  </head>
  <body style="font-family: Georgia, serif; margin: 2rem; color: #1f2937;">
    <main style="max-width: 42rem;">
      <p style="font-size: 0.8rem; letter-spacing: 0.16em; text-transform: uppercase; color: #64748b;">DCX Email Preferences</p>
      <h1 style="margin-bottom: 0.75rem;">{heading}</h1>
      <p>{message}</p>
    </main>
  </body>
</html>"""
