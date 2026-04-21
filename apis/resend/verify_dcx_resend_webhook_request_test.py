import base64
import hashlib
import hmac
import json

from apis.resend.verify_dcx_resend_webhook_request import (
    verify_dcx_resend_webhook_request,
)


def test_verifies_valid_resend_webhook_request(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "whsec_testsecret")
    raw_payload = json.dumps({"type": "email.delivered", "data": {"email_id": "msg_123"}})
    signed_content = f"msg_123.1778000000.{raw_payload}"
    signature = base64.b64encode(
        hmac.new(
            b"testsecret",
            signed_content.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    payload = verify_dcx_resend_webhook_request(
        raw_request_body=raw_payload,
        request_headers={
            "svix-id": "msg_123",
            "svix-timestamp": "1778000000",
            "svix-signature": f"v1,{signature}",
        },
        current_timestamp_seconds_provider=lambda: 1778000001,
    )

    assert payload["type"] == "email.delivered"


def test_rejects_resend_webhook_request_with_invalid_signature(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_WEBHOOK_SECRET", "whsec_testsecret")

    try:
        verify_dcx_resend_webhook_request(
            raw_request_body='{"type":"email.delivered"}',
            request_headers={
                "svix-id": "msg_123",
                "svix-timestamp": "1778000000",
                "svix-signature": "v1,bad_signature",
            },
            current_timestamp_seconds_provider=lambda: 1778000001,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_RESEND_WEBHOOK_INVALID"
    else:  # pragma: no cover - guard
        raise AssertionError("Expected invalid webhook signature error")
