from unittest.mock import patch

import messages.send_dcx_trade_interest_alert_notifications as module_under_test


def test_sends_email_alert_to_matching_interested_user(monkeypatch) -> None:
    sent_emails: list[dict] = []
    delivery_updates: list[dict] = []

    def fake_send_email_notification(recipient_email: str, subject: str, message_text: str) -> dict:
        sent_emails.append(
            {
                "recipient_email": recipient_email,
                "subject": subject,
                "message_text": message_text,
            }
        )
        return {
            "provider_message_id": "email_interest_1",
        }

    with patch.object(
        module_under_test,
        "_read_trade_interest_alert_context",
        return_value={
            "trade_id": 24,
            "owner_user_id": 1,
            "trade_publication_id": 9,
            "is_alert_eligible": True,
            "trade_snapshot": {
                "normalized_trade_side": "sell",
                "normalized_material_name": "Primary Aluminum Ingots",
                "normalized_material_key": "aluminum",
                "normalized_quantity_value": 1000,
                "normalized_quantity_unit": "MT",
                "normalized_price_value": 3525,
                "normalized_price_unit_basis": "MT",
                "normalized_currency_code": "USD",
                "normalized_origin_location": "",
                "normalized_destination_location": "Shanghai, China",
            },
            "material_options": [
                {
                    "material_key": "aluminum",
                    "synonyms": ["aluminum", "aluminium"],
                }
            ],
        },
    ), patch.object(
        module_under_test,
        "_read_interested_trade_alert_recipients",
        return_value=[
            {
                "recipient_user_id": 2,
                "default_interaction_channel": "email",
            }
        ],
    ), patch.object(
        module_under_test,
        "_resolve_trade_interest_alert_route",
        return_value={
            "channel": "email",
            "destination": "buyer@example.com",
            "reason": "email_route",
        },
    ), patch.object(
        module_under_test,
        "_create_trade_interest_alert_delivery",
        return_value=100,
    ), patch.object(
        module_under_test,
        "_mark_trade_interest_alert_delivery",
        side_effect=lambda **kwargs: delivery_updates.append(kwargs),
    ):
        result = module_under_test.send_dcx_trade_interest_alert_notifications(
            trade_id=24,
            trigger_source="trade_published",
            connect_to_database=lambda **_: None,
            send_email_notification=fake_send_email_notification,
        )

    assert result["status"] == "completed"
    assert result["material_key"] == "aluminum"
    assert result["sent_count"] == 1
    assert sent_emails[0]["recipient_email"] == "buyer@example.com"
    assert sent_emails[0]["subject"] == "DCX: Primary Aluminum Ingots matching your interests"
    assert "New DCX trade matching your interests" in sent_emails[0]["message_text"]
    assert "Primary Aluminum Ingots" in sent_emails[0]["message_text"]
    assert "Open:" in sent_emails[0]["message_text"]
    assert delivery_updates[0]["delivery_status"] == "sent"


def test_skips_unconfirmed_trade() -> None:
    with patch.object(
        module_under_test,
        "_read_trade_interest_alert_context",
        return_value={
            "trade_id": 24,
            "owner_user_id": 1,
            "trade_publication_id": 9,
            "is_alert_eligible": False,
            "trade_snapshot": {},
            "material_options": [],
        },
    ):
        result = module_under_test.send_dcx_trade_interest_alert_notifications(
            trade_id=24,
            trigger_source="trade_confirmed",
            connect_to_database=lambda **_: None,
        )

    assert result == {
        "status": "skipped",
        "reason": "trade_not_alert_eligible",
        "sent_count": 0,
    }
