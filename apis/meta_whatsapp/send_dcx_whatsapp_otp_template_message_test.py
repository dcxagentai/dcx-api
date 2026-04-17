from apis.meta_whatsapp.send_dcx_whatsapp_verification_template_message import (
    send_dcx_whatsapp_verification_template_message,
)


def test_meta_whatsapp_otp_adapter_builds_expected_template_payload(monkeypatch) -> None:
    monkeypatch.setenv("META_WHATSAPP_TOKEN", "test_token")
    monkeypatch.setenv("META_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("META_WHATSAPP_VERIFY_TEMPLATE_NAME", "dcx_agentic_verify_account")
    monkeypatch.setenv("META_WHATSAPP_VERIFY_TEMPLATE_LANGUAGE_CODE", "en_US")
    monkeypatch.setenv("META_API_VERSION", "v23.0")

    sent_request = {}

    def _fake_provider_send(request_url: str, request_headers: dict, request_payload: dict) -> dict:
        sent_request["request_url"] = request_url
        sent_request["request_headers"] = request_headers
        sent_request["request_payload"] = request_payload
        return {"messages": [{"id": "wamid.test"}]}

    result = send_dcx_whatsapp_verification_template_message(
        phone_e164="+34600000001",
        template_body_greeting_name="there",
        template_body_verification_target="+34600000001",
        template_button_url_suffix="en/t/verify-whatsapp-phone#whatsapp_phone_link_token=test-token",
        send_payload_with_provider=_fake_provider_send,
    )

    assert result["provider"] == "meta_whatsapp"
    assert result["provider_message_id"] == "wamid.test"
    assert sent_request["request_url"] == "https://graph.facebook.com/v23.0/123456789/messages"
    assert sent_request["request_headers"]["Authorization"] == "Bearer test_token"
    assert sent_request["request_payload"]["to"] == "+34600000001"
    assert sent_request["request_payload"]["template"]["name"] == "dcx_agentic_verify_account"
    assert sent_request["request_payload"]["template"]["components"][0]["parameters"][0]["text"] == "there"
    assert sent_request["request_payload"]["template"]["components"][0]["parameters"][1]["text"] == "+34600000001"
    assert sent_request["request_payload"]["template"]["components"][1]["parameters"][0]["text"] == "en/t/verify-whatsapp-phone#whatsapp_phone_link_token=test-token"


def test_meta_whatsapp_otp_adapter_raises_clear_error_when_required_config_missing(monkeypatch) -> None:
    monkeypatch.delenv("META_WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("META_PHONE_NUMBER_ID", raising=False)
    monkeypatch.delenv("META_WHATSAPP_VERIFY_TEMPLATE_NAME", raising=False)
    monkeypatch.delenv("META_WHATSAPP_VERIFY_TEMPLATE_LANGUAGE_CODE", raising=False)
    monkeypatch.delenv("META_API_VERSION", raising=False)

    try:
        send_dcx_whatsapp_verification_template_message(
            phone_e164="+34600000001",
            template_body_greeting_name="there",
            template_body_verification_target="+34600000001",
            template_button_url_suffix="en/t/verify-whatsapp-phone#whatsapp_phone_link_token=test-token",
        )
    except RuntimeError as exc:
        assert str(exc) == (
            "API_DCX_WHATSAPP_VERIFY_PROVIDER_CONFIGURATION_MISSING:"
            "META_WHATSAPP_TOKEN,META_PHONE_NUMBER_ID,META_WHATSAPP_VERIFY_TEMPLATE_NAME,"
            "META_WHATSAPP_VERIFY_TEMPLATE_LANGUAGE_CODE,META_API_VERSION"
        )
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected missing Meta config to raise a stable runtime error.")


def test_meta_whatsapp_otp_adapter_raises_clear_error_when_provider_send_fails(monkeypatch) -> None:
    monkeypatch.setenv("META_WHATSAPP_TOKEN", "test_token")
    monkeypatch.setenv("META_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("META_WHATSAPP_VERIFY_TEMPLATE_NAME", "dcx_agentic_verify_account")
    monkeypatch.setenv("META_WHATSAPP_VERIFY_TEMPLATE_LANGUAGE_CODE", "en_US")
    monkeypatch.setenv("META_API_VERSION", "v23.0")

    def _failing_provider_send(request_url: str, request_headers: dict, request_payload: dict) -> dict:
        raise RuntimeError("provider down")

    try:
        send_dcx_whatsapp_verification_template_message(
            phone_e164="+34600000001",
            template_body_greeting_name="there",
            template_body_verification_target="+34600000001",
            template_button_url_suffix="en/t/verify-whatsapp-phone#whatsapp_phone_link_token=test-token",
            send_payload_with_provider=_failing_provider_send,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_WHATSAPP_VERIFY_PROVIDER_SEND_FAILED"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected provider failure to raise a stable runtime error.")
