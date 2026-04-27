from messages.process_dcx_meta_whatsapp_inbound_webhook_payload import (
    process_dcx_meta_whatsapp_inbound_webhook_payload,
)


def test_processes_meta_whatsapp_payload_into_stored_message_and_acknowledgement() -> None:
    sent_acknowledgements: list[dict] = []

    result = process_dcx_meta_whatsapp_inbound_webhook_payload(
        webhook_payload={"entry": [{"changes": []}]},
        store_provider_event=lambda **_kwargs: {"provider_event_id": 17, "payload_hash": "hash-1"},
        read_message_envelopes=lambda _payload: [
            {
                "provider_message_id": "wamid.123",
                "source_handle": "34600111222",
                "target_handle": "15551234567",
                "message_format": "text",
                "message_subject": "",
                "raw_text_content": "Hola, tengo trigo disponible.",
                "received_at_ts_ms": 1777000000000,
                "should_send_ack": True,
                "message_metadata_json": {"meta_message_type": "text"},
            }
        ],
        ingest_inbound_envelope=lambda **_kwargs: {
            "message_id": 501,
            "job_id": 601,
            "processing_status": "ready",
            "derivation_status": "completed",
            "normalized_source_handle": "+34600111222",
            "resolved_user_id": 77,
            "resolved_contact_method_id": 91,
            "resolution_status": "matched_contact_method",
        },
        send_whatsapp_text_message=lambda **kwargs: sent_acknowledgements.append(kwargs)
        or {"provider_message_id": "wamid.ack"},
    )

    assert result["status"] == "processed"
    assert result["processed_message_count"] == 1
    assert result["messages"][0]["message_id"] == 501
    assert result["messages"][0]["acknowledgement_status"] == "accepted"
    assert sent_acknowledgements == [
        {
            "phone_e164": "+34600111222",
            "message_text": "Received. I'm analysing this now.",
        }
    ]


def test_processes_meta_whatsapp_media_attachment_into_inbound_attachment_inputs() -> None:
    seen_ingest_calls: list[dict] = []

    result = process_dcx_meta_whatsapp_inbound_webhook_payload(
        webhook_payload={"entry": [{"changes": []}]},
        store_provider_event=lambda **_kwargs: {"provider_event_id": 17, "payload_hash": "hash-1"},
        read_message_envelopes=lambda _payload: [
            {
                "provider_message_id": "wamid.media.123",
                "source_handle": "34600111222",
                "target_handle": "15551234567",
                "message_format": "image",
                "message_subject": "",
                "raw_text_content": "See photo",
                "received_at_ts_ms": 1777000000000,
                "should_send_ack": False,
                "message_metadata_json": {"meta_message_type": "image"},
                "attachment_descriptors": [
                    {
                        "provider_media_id": "media_123",
                        "content_type": "image/jpeg",
                        "original_filename": None,
                    }
                ],
            }
        ],
        read_media_bytes=lambda _media_id: {
            "media_id": "media_123",
            "content_type": "image/jpeg",
            "file_bytes": b"image-bytes",
        },
        ingest_inbound_envelope=lambda **kwargs: seen_ingest_calls.append(kwargs)
        or {
            "message_id": 501,
            "job_id": 601,
            "processing_status": "ready",
            "derivation_status": "completed",
            "normalized_source_handle": "+34600111222",
            "resolved_user_id": 77,
            "resolved_contact_method_id": 91,
            "resolution_status": "matched_contact_method",
        },
    )

    assert result["messages"][0]["acknowledgement_status"] == "not_sent"
    assert seen_ingest_calls[0]["attachment_inputs"] == [
        {
            "original_filename": None,
            "content_type": "image/jpeg",
            "file_bytes": b"image-bytes",
            "provider_media_id": "media_123",
        }
    ]
    assert seen_ingest_calls[0]["message_metadata_json"]["meta_skipped_attachment_reads"] == []


def test_processes_meta_whatsapp_message_when_one_attachment_fetch_fails() -> None:
    seen_ingest_calls: list[dict] = []

    result = process_dcx_meta_whatsapp_inbound_webhook_payload(
        webhook_payload={"entry": [{"changes": []}]},
        store_provider_event=lambda **_kwargs: {"provider_event_id": 17, "payload_hash": "hash-1"},
        read_message_envelopes=lambda _payload: [
            {
                "provider_message_id": "wamid.media.456",
                "source_handle": "34600111222",
                "target_handle": "15551234567",
                "message_format": "mixed",
                "message_subject": "",
                "raw_text_content": "See files",
                "received_at_ts_ms": 1777000000000,
                "should_send_ack": False,
                "message_metadata_json": {"meta_message_type": "document"},
                "attachment_descriptors": [
                    {
                        "provider_media_id": "media_ok",
                        "content_type": "image/jpeg",
                        "original_filename": None,
                    },
                    {
                        "provider_media_id": "media_fail",
                        "content_type": "application/pdf",
                        "original_filename": "offer.pdf",
                    },
                ],
            }
        ],
        read_media_bytes=lambda media_id: (
            {
                "media_id": "media_ok",
                "content_type": "image/jpeg",
                "file_bytes": b"image-bytes",
            }
            if media_id == "media_ok"
            else (_ for _ in ()).throw(RuntimeError("provider media fetch failed"))
        ),
        ingest_inbound_envelope=lambda **kwargs: seen_ingest_calls.append(kwargs)
        or {
            "message_id": 502,
            "job_id": 602,
            "processing_status": "ready",
            "derivation_status": "completed",
            "normalized_source_handle": "+34600111222",
            "resolved_user_id": 77,
            "resolved_contact_method_id": 91,
            "resolution_status": "matched_contact_method",
        },
    )

    assert result["messages"][0]["message_id"] == 502
    assert seen_ingest_calls[0]["attachment_inputs"] == [
        {
            "original_filename": None,
            "content_type": "image/jpeg",
            "file_bytes": b"image-bytes",
            "provider_media_id": "media_ok",
        }
    ]
    assert seen_ingest_calls[0]["message_metadata_json"]["meta_skipped_attachment_reads"] == [
        {
            "index": 2,
            "provider_media_id": "media_fail",
            "original_filename": "offer.pdf",
            "error_code": "API_DCX_META_WHATSAPP_MEDIA_READ_FAILED",
        }
    ]


def test_suppresses_repeated_acknowledgements_for_multi_image_whatsapp_burst() -> None:
    sent_acknowledgements: list[dict] = []

    result = process_dcx_meta_whatsapp_inbound_webhook_payload(
        webhook_payload={"entry": [{"changes": []}]},
        store_provider_event=lambda **_kwargs: {"provider_event_id": 17, "payload_hash": "hash-1"},
        read_message_envelopes=lambda _payload: [
            {
                "provider_message_id": "wamid.image.1",
                "source_handle": "34600111222",
                "target_handle": "15551234567",
                "message_format": "image",
                "message_subject": "",
                "raw_text_content": "",
                "received_at_ts_ms": 1777000000000,
                "should_send_ack": True,
                "message_metadata_json": {"meta_message_type": "image"},
                "attachment_descriptors": [],
            },
            {
                "provider_message_id": "wamid.image.2",
                "source_handle": "34600111222",
                "target_handle": "15551234567",
                "message_format": "image",
                "message_subject": "",
                "raw_text_content": "",
                "received_at_ts_ms": 1777000001000,
                "should_send_ack": True,
                "message_metadata_json": {"meta_message_type": "image"},
                "attachment_descriptors": [],
            },
        ],
        ingest_inbound_envelope=lambda **_kwargs: {
            "message_id": 501,
            "job_id": 601,
            "processing_status": "ready",
            "derivation_status": "completed",
            "normalized_source_handle": "+34600111222",
            "resolved_user_id": 77,
            "resolved_contact_method_id": 91,
            "resolution_status": "matched_contact_method",
        },
        send_whatsapp_text_message=lambda **kwargs: sent_acknowledgements.append(kwargs)
        or {"provider_message_id": "wamid.ack"},
    )

    assert [message["acknowledgement_status"] for message in result["messages"]] == [
        "accepted",
        "suppressed",
    ]
    assert sent_acknowledgements == [
        {
            "phone_e164": "+34600111222",
            "message_text": "Received. I'm analysing this now.",
        }
    ]
