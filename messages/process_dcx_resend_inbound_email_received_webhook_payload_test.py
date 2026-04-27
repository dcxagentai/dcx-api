from messages.process_dcx_resend_inbound_email_received_webhook_payload import (
    process_dcx_resend_inbound_email_received_webhook_payload,
)


def test_processes_resend_received_email_into_canonical_message() -> None:
    seen_ingest_calls: list[dict] = []

    result = process_dcx_resend_inbound_email_received_webhook_payload(
        webhook_payload={
            "type": "email.received",
            "data": {
                "email_id": "rx_123",
                "created_at": "2026-04-21T19:10:00Z",
                "from": "Trader <trader@example.com>",
                "to": ["chat@mail.dcxagent.ai"],
                "subject": "Offer wheat",
            },
        },
        store_provider_event=lambda **_kwargs: {"provider_event_id": 17, "payload_hash": "hash-1"},
        read_received_email_content=lambda _email_id: {
            "id": "rx_123",
            "created_at": "2026-04-21T19:10:00Z",
            "from": "Trader <trader@example.com>",
            "to": ["chat@mail.dcxagent.ai"],
            "subject": "Offer wheat",
            "text": "Offering 5000 MT wheat FOB Rouen.",
            "headers": {"message-id": "<abc123@example.com>"},
        },
        read_received_email_attachment_inputs=lambda _email_id: [],
        ingest_inbound_envelope=lambda **kwargs: seen_ingest_calls.append(kwargs)
        or {
            "message_id": 701,
            "job_id": 801,
            "processing_status": "ready",
            "derivation_status": "completed",
            "resolved_user_id": 77,
            "resolution_status": "matched_contact_method",
        },
    )

    assert result == {
        "status": "processed",
        "provider_event_id": 17,
        "message_id": 701,
        "job_id": 801,
        "processing_status": "ready",
        "derivation_status": "completed",
        "resolved_user_id": 77,
        "resolution_status": "matched_contact_method",
    }
    assert seen_ingest_calls[0]["attachment_inputs"] == []
    assert seen_ingest_calls[0]["message_metadata_json"]["resend_skipped_attachment_reads"] == []


def test_processes_resend_received_email_with_partial_attachment_download_failure() -> None:
    seen_ingest_calls: list[dict] = []

    result = process_dcx_resend_inbound_email_received_webhook_payload(
        webhook_payload={
            "type": "email.received",
            "data": {
                "email_id": "rx_456",
                "created_at": "2026-04-21T20:10:00Z",
                "from": "Trader <trader@example.com>",
                "to": ["chat@mail.dcxagent.ai"],
                "subject": "Offer wheat with files",
            },
        },
        store_provider_event=lambda **_kwargs: {"provider_event_id": 18, "payload_hash": "hash-2"},
        read_received_email_content=lambda _email_id: {
            "id": "rx_456",
            "created_at": "2026-04-21T20:10:00Z",
            "from": "Trader <trader@example.com>",
            "to": ["chat@mail.dcxagent.ai"],
            "subject": "Offer wheat with files",
            "text": "Attached are one offer pdf and one photo.",
            "headers": {"message-id": "<abc456@example.com>"},
        },
        read_received_email_attachment_inputs=lambda _email_id: {
            "attachment_inputs": [
                {
                    "original_filename": "offer.pdf",
                    "content_type": "application/pdf",
                    "file_bytes": b"pdf-bytes",
                    "provider_media_id": "att_1",
                }
            ],
            "skipped_attachment_reads": [
                {
                    "index": 2,
                    "provider_media_id": "att_2",
                    "original_filename": "photo.png",
                    "error_code": "API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_READ_FAILED",
                }
            ],
        },
        ingest_inbound_envelope=lambda **kwargs: seen_ingest_calls.append(kwargs)
        or {
            "message_id": 702,
            "job_id": 802,
            "processing_status": "ready",
            "derivation_status": "completed",
            "resolved_user_id": 77,
            "resolution_status": "matched_contact_method",
        },
    )

    assert result == {
        "status": "processed",
        "provider_event_id": 18,
        "message_id": 702,
        "job_id": 802,
        "processing_status": "ready",
        "derivation_status": "completed",
        "resolved_user_id": 77,
        "resolution_status": "matched_contact_method",
    }
    assert seen_ingest_calls[0]["attachment_inputs"] == [
        {
            "original_filename": "offer.pdf",
            "content_type": "application/pdf",
            "file_bytes": b"pdf-bytes",
            "provider_media_id": "att_1",
        }
    ]
    assert seen_ingest_calls[0]["message_metadata_json"]["resend_skipped_attachment_reads"] == [
        {
            "index": 2,
            "provider_media_id": "att_2",
            "original_filename": "photo.png",
            "error_code": "API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_READ_FAILED",
        }
    ]


def test_raises_for_non_received_resend_event() -> None:
    try:
        process_dcx_resend_inbound_email_received_webhook_payload(
            webhook_payload={"type": "email.delivered", "data": {"email_id": "rx_123"}}
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_RESEND_INBOUND_EMAIL_EVENT_INVALID"
    else:
        raise AssertionError("Expected non-email.received event to raise")
