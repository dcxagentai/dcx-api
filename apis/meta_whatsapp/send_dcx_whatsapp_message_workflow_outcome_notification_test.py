import pytest

from apis.meta_whatsapp import send_dcx_whatsapp_message_workflow_outcome_notification as module_under_test


def test_sends_one_outcome_text_message(monkeypatch) -> None:
    sent_messages: list[dict] = []

    def fake_send_dcx_whatsapp_text_message(phone_e164: str, message_text: str) -> dict:
        sent_messages.append(
            {
                "phone_e164": phone_e164,
                "message_text": message_text,
            }
        )
        return {
            "provider": "meta_whatsapp",
            "status": "accepted",
            "provider_message_id": "wamid.outbound.123",
        }

    monkeypatch.setattr(module_under_test, "send_dcx_whatsapp_text_message", fake_send_dcx_whatsapp_text_message)

    result = module_under_test.send_dcx_whatsapp_message_workflow_outcome_notification(
        phone_e164=" +34600000001 ",
        message_text=" DCX processed your message. ",
    )

    assert result["status"] == "accepted"
    assert sent_messages == [
        {
            "phone_e164": "+34600000001",
            "message_text": "DCX processed your message.",
        }
    ]


def test_rejects_blank_inputs() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        module_under_test.send_dcx_whatsapp_message_workflow_outcome_notification(
            phone_e164="",
            message_text="DCX processed your message.",
        )

    assert str(exc_info.value) == "API_DCX_WHATSAPP_WORKFLOW_OUTCOME_MESSAGE_INVALID"
