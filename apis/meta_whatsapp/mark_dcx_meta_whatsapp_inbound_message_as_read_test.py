import pytest

from apis.meta_whatsapp.mark_dcx_meta_whatsapp_inbound_message_as_read import (
    mark_dcx_meta_whatsapp_inbound_message_as_read,
)


def test_meta_whatsapp_read_receipt_adapter_builds_expected_payload(monkeypatch) -> None:
    sent_requests: list[dict] = []
    monkeypatch.setenv("META_WHATSAPP_TOKEN", "test-token")
    monkeypatch.setenv("META_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("META_API_VERSION", "v20.0")

    result = mark_dcx_meta_whatsapp_inbound_message_as_read(
        provider_message_id="wamid.inbound.123",
        mark_payload_with_provider=lambda request_url, request_headers, request_payload: sent_requests.append(
            {
                "request_url": request_url,
                "request_headers": request_headers,
                "request_payload": request_payload,
            }
        )
        or {"success": True},
    )

    assert result["provider"] == "meta_whatsapp"
    assert result["status"] == "accepted"
    assert sent_requests == [
        {
            "request_url": "https://graph.facebook.com/v20.0/123456789/messages",
            "request_headers": {
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
            },
            "request_payload": {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": "wamid.inbound.123",
            },
        }
    ]


def test_meta_whatsapp_read_receipt_adapter_raises_clear_error_when_required_config_missing(
    monkeypatch,
) -> None:
    monkeypatch.delenv("META_WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("META_PHONE_NUMBER_ID", raising=False)
    monkeypatch.delenv("META_API_VERSION", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        mark_dcx_meta_whatsapp_inbound_message_as_read(provider_message_id="wamid.inbound.123")

    assert str(exc_info.value) == (
        "API_DCX_WHATSAPP_READ_RECEIPT_PROVIDER_CONFIGURATION_MISSING:"
        "META_WHATSAPP_TOKEN,META_PHONE_NUMBER_ID,META_API_VERSION"
    )


def test_meta_whatsapp_read_receipt_adapter_raises_clear_error_when_provider_send_fails(
    monkeypatch,
) -> None:
    monkeypatch.setenv("META_WHATSAPP_TOKEN", "test-token")
    monkeypatch.setenv("META_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("META_API_VERSION", "v20.0")

    with pytest.raises(RuntimeError) as exc_info:
        mark_dcx_meta_whatsapp_inbound_message_as_read(
            provider_message_id="wamid.inbound.123",
            mark_payload_with_provider=lambda *_args: (_ for _ in ()).throw(RuntimeError("provider down")),
        )

    assert str(exc_info.value) == "API_DCX_WHATSAPP_READ_RECEIPT_PROVIDER_SEND_FAILED"
