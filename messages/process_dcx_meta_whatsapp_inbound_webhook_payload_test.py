from messages.process_dcx_meta_whatsapp_inbound_webhook_payload import (
    process_dcx_meta_whatsapp_inbound_webhook_payload,
)


def test_processes_meta_whatsapp_payload_into_stored_message_and_read_receipt() -> None:
    marked_messages: list[dict] = []

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
                "should_mark_read": True,
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
        mark_whatsapp_message_as_read=lambda **kwargs: marked_messages.append(kwargs)
        or {"status": "accepted"},
    )

    assert result["status"] == "processed"
    assert result["processed_message_count"] == 1
    assert result["messages"][0]["message_id"] == 501
    assert result["messages"][0]["read_receipt_status"] == "accepted"
    assert result["messages"][0]["acknowledgement_status"] == "accepted"
    assert marked_messages == [
        {
            "provider_message_id": "wamid.123",
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
                "should_mark_read": False,
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
                "should_mark_read": False,
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


def test_marks_each_image_in_multi_image_whatsapp_burst_as_read_without_sending_text() -> None:
    marked_messages: list[dict] = []

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
                "should_mark_read": True,
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
                "should_mark_read": True,
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
        mark_whatsapp_message_as_read=lambda **kwargs: marked_messages.append(kwargs)
        or {"status": "accepted"},
    )

    assert [message["read_receipt_status"] for message in result["messages"]] == [
        "accepted",
        "accepted",
    ]
    assert marked_messages == [
        {"provider_message_id": "wamid.image.1"},
        {"provider_message_id": "wamid.image.2"},
    ]


def test_processes_meta_whatsapp_outbound_status_webhook_event() -> None:
    recorded_events: list[dict] = []

    result = process_dcx_meta_whatsapp_inbound_webhook_payload(
        webhook_payload={"entry": [{"changes": []}]},
        store_provider_event=lambda **_kwargs: {"provider_event_id": 17, "payload_hash": "hash-1"},
        read_message_envelopes=lambda _payload: [],
        read_outbound_status_events=lambda _payload: [
            {
                "provider_message_id": "wamid.outbound.123",
                "provider_status": "failed",
                "status_timestamp_ms": 1777744000000,
                "recipient_id": "34647818143",
                "errors": [
                    {
                        "code": 131047,
                        "title": "Re-engagement message",
                    }
                ],
                "conversation": {},
                "pricing": {},
            }
        ],
        record_outbound_status_event=lambda status_event: recorded_events.append(status_event)
        or {
            "status": "recorded",
            "outbound_route_id": 9,
            "provider_message_id": status_event["provider_message_id"],
            "provider_status": status_event["provider_status"],
        },
    )

    assert result["processed_message_count"] == 0
    assert result["outbound_status_event_count"] == 1
    assert result["recorded_outbound_status_event_count"] == 1
    assert recorded_events[0]["provider_message_id"] == "wamid.outbound.123"
    assert recorded_events[0]["provider_status"] == "failed"
