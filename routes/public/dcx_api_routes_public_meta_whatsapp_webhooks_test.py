from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.public.dcx_api_routes_public_meta_whatsapp_webhooks as public_meta_whatsapp_webhook_routes

client = TestClient(app)


def test_meta_whatsapp_webhook_handshake_returns_challenge_for_valid_token(monkeypatch) -> None:
    monkeypatch.setenv("META_WHATSAPP_WEBHOOK_VERIFY_TOKEN", "dcx-token")

    response = client.get(
        "/public/webhooks/meta-whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "dcx-token",
            "hub.challenge": "123456",
        },
    )

    assert response.status_code == 200
    assert response.text == "123456"


def test_meta_whatsapp_webhook_post_accepts_verified_payload_for_background_processing() -> None:
    with patch.object(
        public_meta_whatsapp_webhook_routes,
        "verify_dcx_meta_whatsapp_webhook_signature",
        return_value={"entry": [{"changes": []}]},
    ), patch.object(
        public_meta_whatsapp_webhook_routes,
        "process_dcx_meta_whatsapp_inbound_webhook_payload",
        return_value={
            "status": "processed",
            "provider_event_id": 88,
            "processed_message_count": 1,
            "messages": [{"message_id": 501, "acknowledgement_status": "accepted"}],
        },
    ) as process_inbound_whatsapp:
        response = client.post(
            "/public/webhooks/meta-whatsapp",
            content='{"entry":[{"changes":[]}]}',
            headers={"X-Hub-Signature-256": "sha256=test"},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["data"]["status"] == "accepted"
    process_inbound_whatsapp.assert_called_once_with(webhook_payload={"entry": [{"changes": []}]})


def test_meta_whatsapp_webhook_post_rejects_invalid_signature() -> None:
    with patch.object(
        public_meta_whatsapp_webhook_routes,
        "verify_dcx_meta_whatsapp_webhook_signature",
        side_effect=RuntimeError("API_DCX_META_WHATSAPP_WEBHOOK_INVALID"),
    ):
        response = client.post(
            "/public/webhooks/meta-whatsapp",
            content='{"entry":[]}',
        )
        payload = response.json()

    assert response.status_code == 400
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_META_WHATSAPP_WEBHOOK_INVALID",
            "message": "We could not process that Meta WhatsApp webhook event.",
            "suggested_action": "Retry once the webhook request is valid and the backend is healthy.",
        },
    }
