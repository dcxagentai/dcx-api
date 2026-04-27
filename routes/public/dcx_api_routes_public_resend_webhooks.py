"""
CONTEXT:
This file owns the public Resend webhook ingestion boundary for DCX.
It exists so verified provider webhook events can update recipient delivery state and suppression
records inside the backend.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from apis.resend.verify_dcx_resend_webhook_request import (
    verify_dcx_resend_webhook_request,
)
from emails.apply_dcx_resend_email_event_to_send_records import (
    apply_dcx_resend_email_event_to_send_records_capability,
)
from messages.process_dcx_resend_inbound_email_received_webhook_payload import (
    process_dcx_resend_inbound_email_received_webhook_payload,
)

dcx_api_routes_public_resend_webhooks_router = APIRouter(
    prefix="/public/webhooks",
    tags=["public_webhooks"],
)


@dcx_api_routes_public_resend_webhooks_router.post("/resend")
async def post_dcx_public_resend_webhook_event(request: Request) -> JSONResponse:
    """
    CONTRACT:
      preconditions:
        - The request is one real webhook POST from Resend.
        - The raw request body is available for signature verification.
        - RESEND_WEBHOOK_SECRET is configured in the backend environment.
      postconditions:
        - Returns `200` with one canonical success wrapper when the webhook is valid, including ignored events.
        - Returns one canonical error wrapper when the webhook is invalid or cannot be applied.
      side_effects:
        - may update recipient delivery rows
        - may create or update suppression rows
      idempotent: true
      retry_safe: true
      async: true
      idempotency_key: resend_webhook:{svix_id}
      locks: []
      contention_strategy: delegates deterministic state convergence to the webhook apply capability

    NARRATIVE:
      WHY this exists:
        - Newsletter delivery state should be driven by provider truth after the initial send request.
      WHEN TO USE it:
        - Use it only as the Resend webhook endpoint registered in the Resend dashboard.
      WHEN NOT TO USE it:
        - Do not use it for browser traffic or admin interactions.
      WHAT CAN GO WRONG:
        - Signature verification can fail.
        - The webhook secret can be missing.
        - The database can be unavailable.
      WHAT COMES NEXT:
        - The admin UI and future reporting can read truer delivery and suppression state.

    TESTS:
      - resend_webhook_route_returns_success_for_verified_payload
      - resend_webhook_route_rejects_invalid_signature

    ERRORS:
      - API_DCX_RESEND_WEBHOOK_INVALID:
          suggested_action: Retry with a genuine Resend webhook request.
          common_causes:
            - invalid signature
            - malformed payload
          recovery_steps:
            - Confirm the raw body is used for verification.
            - Confirm the endpoint secret matches Resend.
          retry_safe: true

    CODE:
    """
    raw_body_bytes = await request.body()
    raw_body = raw_body_bytes.decode("utf-8")

    try:
        verified_payload = verify_dcx_resend_webhook_request(
            raw_request_body=raw_body,
            request_headers=request.headers,
        )
        if (verified_payload.get("type") or "").strip() == "email.received":
            applied_payload = process_dcx_resend_inbound_email_received_webhook_payload(
                webhook_payload=verified_payload,
            )
        else:
            applied_payload = apply_dcx_resend_email_event_to_send_records_capability(
                webhook_payload=verified_payload,
            )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = (
            400
            if error_code in {
                "API_DCX_RESEND_WEBHOOK_INVALID",
                "API_DCX_RESEND_WEBHOOK_EXPIRED",
                "API_DCX_RESEND_EMAIL_EVENT_INVALID",
                "API_DCX_RESEND_INBOUND_EMAIL_EVENT_INVALID",
            }
            else 503
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not process that Resend webhook event.",
                    "suggested_action": "Retry once the webhook request is valid and the backend is healthy.",
                },
            },
        )

    return JSONResponse(
        content={
            "ok": True,
            "data": applied_payload,
            "context": {
                "surface": "public",
                "view": "resend_webhook_event",
            },
        }
    )
