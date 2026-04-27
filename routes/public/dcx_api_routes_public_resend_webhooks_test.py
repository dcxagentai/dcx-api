"""
CONTEXT:
This file verifies the DCX public Resend webhook route.
It keeps the verified-success and invalid-webhook behavior executable while email operations grow.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.public.dcx_api_routes_public_resend_webhooks as public_resend_webhook_routes

client = TestClient(app)


def test_resend_webhook_route_returns_success_for_verified_payload() -> None:
    with patch.object(
        public_resend_webhook_routes,
        "verify_dcx_resend_webhook_request",
        return_value={"type": "email.delivered", "data": {"email_id": "msg_123"}},
    ), patch.object(
        public_resend_webhook_routes,
        "apply_dcx_resend_email_event_to_send_records_capability",
        return_value={
            "status": "applied",
            "event_type": "email.delivered",
            "provider_message_id": "msg_123",
            "email_send_id": 501,
            "recipient_id": 701,
        },
    ):
        response = client.post(
            "/public/webhooks/resend",
            content='{"type":"email.delivered","data":{"email_id":"msg_123"}}',
            headers={"svix-id": "msg_1", "svix-timestamp": "1778000000", "svix-signature": "v1,signature"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["status"] == "applied"


def test_resend_webhook_route_routes_email_received_into_inbound_message_processing() -> None:
    with patch.object(
        public_resend_webhook_routes,
        "verify_dcx_resend_webhook_request",
        return_value={"type": "email.received", "data": {"email_id": "rx_123"}},
    ), patch.object(
        public_resend_webhook_routes,
        "process_dcx_resend_inbound_email_received_webhook_payload",
        return_value={
            "status": "processed",
            "provider_event_id": 88,
            "message_id": 501,
            "job_id": 601,
            "processing_status": "ready",
            "derivation_status": "completed",
            "resolved_user_id": 77,
            "resolution_status": "matched_contact_method",
        },
    ) as process_inbound_email:
        response = client.post(
            "/public/webhooks/resend",
            content='{"type":"email.received","data":{"email_id":"rx_123"}}',
            headers={"svix-id": "msg_1", "svix-timestamp": "1778000000", "svix-signature": "v1,signature"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["status"] == "processed"
    process_inbound_email.assert_called_once_with(
        webhook_payload={"type": "email.received", "data": {"email_id": "rx_123"}}
    )


def test_resend_webhook_route_rejects_invalid_signature() -> None:
    with patch.object(
        public_resend_webhook_routes,
        "verify_dcx_resend_webhook_request",
        side_effect=RuntimeError("API_DCX_RESEND_WEBHOOK_INVALID"),
    ):
        response = client.post(
            "/public/webhooks/resend",
            content='{"type":"email.delivered"}',
        )
        payload = response.json()

    assert response.status_code == 400
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_RESEND_WEBHOOK_INVALID",
            "message": "We could not process that Resend webhook event.",
            "suggested_action": "Retry once the webhook request is valid and the backend is healthy.",
        },
    }
