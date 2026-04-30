"""
CONTEXT:
This file owns the public Meta WhatsApp webhook ingestion boundary for DCX.
It exists so verified inbound WhatsApp messages can become stored, derived DCX contact messages.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from apis.meta_whatsapp.verify_dcx_meta_whatsapp_webhook_signature import (
    verify_dcx_meta_whatsapp_webhook_signature,
)
from messages.process_dcx_meta_whatsapp_inbound_webhook_payload import (
    process_dcx_meta_whatsapp_inbound_webhook_payload,
)

dcx_api_routes_public_meta_whatsapp_webhooks_router = APIRouter(
    prefix="/public/webhooks",
    tags=["public_webhooks"],
)


@dcx_api_routes_public_meta_whatsapp_webhooks_router.get("/meta-whatsapp")
def get_dcx_public_meta_whatsapp_webhook_handshake(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    """
    CONTRACT:
      preconditions:
        - Meta is validating the configured webhook URL with the standard WhatsApp webhook GET challenge.
        - META_WHATSAPP_WEBHOOK_VERIFY_TOKEN is configured in the backend environment.
      postconditions:
        - Returns the raw challenge string when the verify token matches.
        - Returns one canonical error wrapper when the token is invalid.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Meta requires a GET challenge handshake before it will deliver inbound WhatsApp events.
      WHEN TO USE it:
        - Use it only as the callback verification URL configured in Meta.
      WHEN NOT TO USE it:
        - Do not use it for browser traffic or message ingestion.
      WHAT CAN GO WRONG:
        - The verify token can be missing or wrong.
      WHAT COMES NEXT:
        - Once verified, Meta can POST real inbound message events to the paired POST route.

    TESTS:
      - meta_whatsapp_webhook_handshake_returns_challenge_for_valid_token
      - meta_whatsapp_webhook_handshake_rejects_invalid_token

    ERRORS:
      - API_DCX_META_WHATSAPP_WEBHOOK_HANDSHAKE_INVALID:
          suggested_action: Retry the Meta webhook setup with the correct verify token.
          common_causes:
            - missing META_WHATSAPP_WEBHOOK_VERIFY_TOKEN
            - wrong verify token in Meta
          recovery_steps:
            - Confirm META_WHATSAPP_WEBHOOK_VERIFY_TOKEN in the backend environment.
            - Re-enter the same token in Meta.
          retry_safe: true

    CODE:
    """
    configured_verify_token = os.getenv("META_WHATSAPP_WEBHOOK_VERIFY_TOKEN", "").strip()
    if hub_mode == "subscribe" and configured_verify_token != "" and hub_verify_token == configured_verify_token:
        return PlainTextResponse(content=hub_challenge or "")

    return JSONResponse(
        status_code=403,
        content={
            "ok": False,
            "error": {
                "code": "API_DCX_META_WHATSAPP_WEBHOOK_HANDSHAKE_INVALID",
                "message": "We could not verify that Meta WhatsApp webhook handshake.",
                "suggested_action": "Retry the webhook setup with the correct verify token.",
            },
        },
    )


@dcx_api_routes_public_meta_whatsapp_webhooks_router.post("/meta-whatsapp")
async def post_dcx_public_meta_whatsapp_webhook_event(
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """
    CONTRACT:
      preconditions:
        - The request is one real Meta WhatsApp webhook POST.
        - The raw request body is available for signature verification.
        - META_APP_SECRET is configured in the backend environment.
      postconditions:
        - Returns `200` with one canonical success wrapper as soon as the webhook is verified and accepted.
        - Schedules the heavier provider-event store, canonical message ingest, media download, and
          read-receipt and workflow-processing work in one background task.
        - Returns one canonical error wrapper when the webhook is invalid or cannot be processed.
      side_effects:
        - enqueues one background task
        - background execution may store provider-event rows
        - background execution may store contact-message rows
        - background execution may mark inbound WhatsApp messages as read and may send workflow follow-ups
      idempotent: true
      retry_safe: true
      async: true

    NARRATIVE:
      WHY this exists:
        - Inbound WhatsApp messages are one of the three first-class trader entry paths for DCX.
      WHEN TO USE it:
        - Use it only as the Meta WhatsApp webhook endpoint.
      WHEN NOT TO USE it:
        - Do not use it for browser traffic or admin actions.
      WHAT CAN GO WRONG:
        - Signature verification can fail.
        - The payload can contain no inbound messages.
        - Background message ingestion can fail after the webhook is accepted.
      WHAT COMES NEXT:
        - Stored inbound WhatsApp messages can appear in the trader Messages inbox and later feed trade classification.

    TESTS:
      - meta_whatsapp_webhook_post_accepts_verified_payload_for_background_processing
      - meta_whatsapp_webhook_post_rejects_invalid_signature

    ERRORS:
      - API_DCX_META_WHATSAPP_WEBHOOK_INVALID:
          suggested_action: Retry with a genuine signed Meta webhook request.
          common_causes:
            - missing or invalid X-Hub-Signature-256
            - malformed JSON body
          recovery_steps:
            - Confirm the raw request body is used for verification.
            - Confirm META_APP_SECRET matches the Meta app.
          retry_safe: true

    CODE:
    """
    raw_body_bytes = await request.body()

    try:
        verified_payload = verify_dcx_meta_whatsapp_webhook_signature(
            raw_request_body=raw_body_bytes,
            signature_header_value=request.headers.get("X-Hub-Signature-256"),
        )
        background_tasks.add_task(
            process_dcx_meta_whatsapp_inbound_webhook_payload,
            webhook_payload=verified_payload,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = (
            400
            if error_code in {
                "API_DCX_META_WHATSAPP_WEBHOOK_INVALID",
                "API_DCX_META_WHATSAPP_WEBHOOK_SECRET_MISSING",
            }
            else 503
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not process that Meta WhatsApp webhook event.",
                    "suggested_action": "Retry once the webhook request is valid and the backend is healthy.",
                },
            },
        )

    return JSONResponse(
        content={
            "ok": True,
            "data": {
                "status": "accepted",
            },
            "context": {
                "surface": "public",
                "view": "meta_whatsapp_webhook_event",
            },
        }
    )
