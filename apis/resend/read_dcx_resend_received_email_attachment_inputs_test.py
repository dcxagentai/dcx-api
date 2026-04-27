from apis.resend.read_dcx_resend_received_email_attachment_inputs import (
    read_dcx_resend_received_email_attachment_fetch_result,
)


def test_returns_attachment_inputs_and_skips_failed_downloads(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")

    result = read_dcx_resend_received_email_attachment_fetch_result(
        received_email_id="rx_123",
        list_received_email_attachments_with_provider=lambda _email_id, _headers: [
            {
                "id": "att_1",
                "filename": "offer.pdf",
                "content_type": "application/pdf",
                "download_url": "https://download.example.com/offer.pdf",
            },
            {
                "id": "att_2",
                "filename": "photo.png",
                "content_type": "image/png",
                "download_url": "https://download.example.com/photo.png",
            },
        ],
        download_attachment_bytes_with_provider=lambda download_url: (
            b"pdf-bytes"
            if download_url.endswith("offer.pdf")
            else (_ for _ in ()).throw(RuntimeError("download failed"))
        ),
    )

    assert result["attachment_inputs"] == [
        {
            "original_filename": "offer.pdf",
            "content_type": "application/pdf",
            "file_bytes": b"pdf-bytes",
            "provider_media_id": "att_1",
        }
    ]
    assert result["skipped_attachment_reads"] == [
        {
            "index": 2,
            "provider_media_id": "att_2",
            "original_filename": "photo.png",
            "error_code": "API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_READ_FAILED",
        }
    ]


def test_skips_attachment_when_download_url_is_missing(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")

    result = read_dcx_resend_received_email_attachment_fetch_result(
        received_email_id="rx_123",
        list_received_email_attachments_with_provider=lambda _email_id, _headers: [
            {
                "id": "att_1",
                "filename": "offer.pdf",
                "content_type": "application/pdf",
                "download_url": "",
            }
        ],
        download_attachment_bytes_with_provider=lambda _download_url: b"unused",
    )

    assert result["attachment_inputs"] == []
    assert result["skipped_attachment_reads"] == [
        {
            "index": 1,
            "provider_media_id": "att_1",
            "original_filename": "offer.pdf",
            "error_code": "API_DCX_RESEND_RECEIVED_EMAIL_ATTACHMENT_DOWNLOAD_URL_MISSING",
        }
    ]
