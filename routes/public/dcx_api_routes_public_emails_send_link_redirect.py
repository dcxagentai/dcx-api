"""
CONTEXT:
This file owns the public tracked-email-link redirect boundary for DCX.
It exists so newsletter emails can route clicks through the API, record one click event, and then
redirect the browser to the original destination URL.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from emails.send_links.record_dcx_email_send_link_click_and_read_redirect_target import (
    record_dcx_email_send_link_click_and_read_redirect_target_capability,
)

dcx_api_routes_public_emails_send_link_redirect_router = APIRouter(
    prefix="/public/email-links",
    tags=["public_email_links"],
)


@dcx_api_routes_public_emails_send_link_redirect_router.get("/{tracking_token}")
def get_dcx_public_email_send_link_redirect(
    tracking_token: str,
    request: Request,
):
    """
    CONTRACT:
      preconditions:
        - tracking_token is one tracked email-link token received from a DCX email.
        - The configured database is reachable.
      postconditions:
        - Records one click event when the tracked token exists.
        - Redirects the client to the original outbound URL for that tracked token.
        - Returns one canonical error wrapper when the token is invalid or unknown.
      side_effects:
        - inserts one link-click row
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: append-only click logging allows concurrent requests to record separate click rows without shared-state contention

    NARRATIVE:
      WHY this exists:
        - Email clicks need one public redirect surface that records engagement before handing the browser off.
      WHEN TO USE it:
        - Use it only for tracked links embedded into DCX outbound emails.
      WHEN NOT TO USE it:
        - Do not use it as a general-purpose public redirect service.
      WHAT CAN GO WRONG:
        - The tracking token can be stale or malformed.
        - The database can be unavailable.
        - Email-security scanners may trigger clicks before a human reader arrives.
      WHAT COMES NEXT:
        - The newsletter dispatcher can now emit tracked URLs instead of the original destinations.

    TESTS:
      - tracked_email_link_route_redirects_for_valid_token
      - tracked_email_link_route_returns_not_found_for_unknown_token

    ERRORS:
      - API_DCX_EMAIL_SEND_LINK_REDIRECT_INVALID:
          suggested_action: Retry from the full tracked link in the email.
          common_causes:
            - malformed tracking token
          recovery_steps:
            - Open the original email.
            - Retry with the full tracked URL.
          retry_safe: true
      - API_DCX_EMAIL_SEND_LINK_REDIRECT_NOT_FOUND:
          suggested_action: Reopen the original email and retry the tracked link.
          common_causes:
            - stale tracking token
            - copied partial URL
          recovery_steps:
            - Use the most recent email copy.
            - Retry from the exact tracked URL.
          retry_safe: true

    CODE:
    """
    request_ip = request.client.host if request.client is not None else None
    request_user_agent = request.headers.get("user-agent")

    try:
        redirect_target = record_dcx_email_send_link_click_and_read_redirect_target_capability(
            tracking_token=tracking_token,
            request_ip=request_ip,
            request_user_agent=request_user_agent,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = (
            400
            if error_code == "API_DCX_EMAIL_SEND_LINK_REDIRECT_INVALID"
            else 404
            if error_code == "API_DCX_EMAIL_SEND_LINK_REDIRECT_NOT_FOUND"
            else 500
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not resolve that tracked email link.",
                    "suggested_action": "Retry from the original email once the tracked link is valid and the backend is healthy.",
                },
            },
        )

    return RedirectResponse(
        url=redirect_target["original_url"],
        status_code=307,
        headers={"Cache-Control": "no-store"},
    )
