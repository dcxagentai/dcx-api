from apis.meta_whatsapp.read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload import (
    read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload,
)


def test_returns_supported_image_message_envelope_with_attachment_descriptor() -> None:
    envelopes = read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"display_phone_number": "15551234567"},
                                "contacts": [{"profile": {"name": "Trader"}}],
                                "messages": [
                                    {
                                        "id": "wamid.image.123",
                                        "from": "34600111222",
                                        "timestamp": "1777000000",
                                        "type": "image",
                                        "image": {
                                            "id": "media_123",
                                            "mime_type": "image/jpeg",
                                            "caption": "Look at this chart",
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
    )

    assert envelopes == [
        {
            "provider_message_id": "wamid.image.123",
            "source_handle": "34600111222",
            "target_handle": "15551234567",
            "message_format": "image",
            "message_subject": "",
            "raw_text_content": "Look at this chart",
            "received_at_ts_ms": 1777000000000,
            "should_mark_read": True,
            "message_metadata_json": {
                "meta_message_type": "image",
                "meta_contact_profile_name": "Trader",
                "meta_context": {},
                "meta_contacts": [{"profile": {"name": "Trader"}}],
            },
            "attachment_descriptors": [
                {
                    "provider_media_id": "media_123",
                    "content_type": "image/jpeg",
                    "original_filename": None,
                }
            ],
        }
    ]


def test_ignores_unsupported_empty_whatsapp_wrapper_message() -> None:
    envelopes = read_dcx_meta_whatsapp_inbound_message_envelopes_from_webhook_payload(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"display_phone_number": "15551234567"},
                                "messages": [
                                    {
                                        "id": "wamid.unsupported.123",
                                        "from": "34600111222",
                                        "timestamp": "1777000000",
                                        "type": "sticker",
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }
    )

    assert envelopes == []
