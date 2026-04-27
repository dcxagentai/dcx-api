from uuid import UUID

from messages.store_dcx_contact_message_attachment_file_object import (
    store_dcx_contact_message_attachment_file_object,
)


class _FakeCursor:
    def __init__(self, fetchone_values):
        self.fetchone_values = list(fetchone_values)
        self.executed_sql = []

    def execute(self, sql, params=None):
        self.executed_sql.append((" ".join(sql.split()), params))

    def fetchone(self):
        if not self.fetchone_values:
            return None
        return self.fetchone_values.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_stores_supported_attachment_into_r2_and_database(monkeypatch) -> None:
    uploaded_objects: list[dict] = []
    monkeypatch.setenv("DCX_R2_APP_BUCKET_NAME", "dcx-app-bucket")

    class _FakeR2Client:
        def put_object(self, **kwargs):
            uploaded_objects.append(kwargs)

    fake_connection = _FakeConnection(_FakeCursor([(8001,), (9001,)]))

    result = store_dcx_contact_message_attachment_file_object(
        message_id=77,
        owner_user_id=5,
        source_channel_type="app",
        source_provider_type="dcx_app",
        original_filename="offer.pdf",
        file_bytes=b"pdf-bytes",
        content_type="application/pdf",
        connect_to_database=lambda **_kwargs: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000000,
        build_r2_client=lambda: _FakeR2Client(),
        file_uuid_provider=lambda: UUID("00000000-0000-0000-0000-000000000801"),
    )

    assert result["attachment_id"] == 9001
    assert result["file_object_id"] == 8001
    assert result["file_uuid"] == "00000000-0000-0000-0000-000000000801"
    assert result["file_kind"] == "document"
    assert uploaded_objects[0]["Bucket"] is not None
    assert "/" not in uploaded_objects[0]["Key"]
    assert len(uploaded_objects[0]["Key"]) == 32
    assert uploaded_objects[0]["ContentType"] == "application/pdf"
    assert any(
        "INSERT INTO stephen_dcx_file_objects" in statement[0]
        for statement in fake_connection.cursor_instance.executed_sql
    )


def test_stores_whatsapp_voice_note_with_parameterized_ogg_content_type(monkeypatch) -> None:
    uploaded_objects: list[dict] = []
    monkeypatch.setenv("DCX_R2_APP_BUCKET_NAME", "dcx-app-bucket")

    class _FakeR2Client:
        def put_object(self, **kwargs):
            uploaded_objects.append(kwargs)

    fake_connection = _FakeConnection(_FakeCursor([None, (8002,), (9002,)]))

    result = store_dcx_contact_message_attachment_file_object(
        message_id=88,
        owner_user_id=5,
        source_channel_type="whatsapp",
        source_provider_type="meta_whatsapp",
        original_filename=None,
        file_bytes=b"ogg-opus-bytes",
        content_type="audio/ogg; codecs=opus",
        provider_media_id="whatsapp-audio-media-id",
        connect_to_database=lambda **_kwargs: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000000,
        build_r2_client=lambda: _FakeR2Client(),
        file_uuid_provider=lambda: UUID("00000000-0000-0000-0000-000000000802"),
    )

    assert result["attachment_id"] == 9002
    assert result["file_uuid"] == "00000000-0000-0000-0000-000000000802"
    assert result["file_kind"] == "audio"
    assert result["content_type"] == "audio/ogg"
    assert result["original_filename"] == ""
    assert "/" not in uploaded_objects[0]["Key"]
    assert len(uploaded_objects[0]["Key"]) == 32
    assert uploaded_objects[0]["ContentType"] == "audio/ogg"


def test_reuses_existing_provider_attachment_without_second_r2_upload(monkeypatch) -> None:
    uploaded_objects: list[dict] = []
    monkeypatch.setenv("DCX_R2_APP_BUCKET_NAME", "dcx-app-bucket")

    class _FakeR2Client:
        def put_object(self, **kwargs):
            uploaded_objects.append(kwargs)

    fake_connection = _FakeConnection(
        _FakeCursor(
            [
                (
                    9002,
                    8002,
                    UUID("00000000-0000-0000-0000-000000000802"),
                    "audio",
                    "audio/ogg",
                    "",
                    14,
                    "app",
                    "existing-r2-key",
                    "whatsapp-audio-media-id",
                    1,
                )
            ]
        )
    )

    result = store_dcx_contact_message_attachment_file_object(
        message_id=88,
        owner_user_id=5,
        source_channel_type="whatsapp",
        source_provider_type="meta_whatsapp",
        original_filename=None,
        file_bytes=b"ogg-opus-bytes",
        content_type="audio/ogg; codecs=opus",
        provider_media_id="whatsapp-audio-media-id",
        connect_to_database=lambda **_kwargs: fake_connection,
        build_r2_client=lambda: _FakeR2Client(),
    )

    assert result["attachment_id"] == 9002
    assert result["file_object_id"] == 8002
    assert result["file_uuid"] == "00000000-0000-0000-0000-000000000802"
    assert result["is_duplicate_provider_attachment"] is True
    assert uploaded_objects == []


def test_raises_when_attachment_exceeds_size_limit(monkeypatch) -> None:
    monkeypatch.setenv("DCX_CONTACT_MESSAGE_ATTACHMENT_MAX_BYTES", "4")

    try:
        store_dcx_contact_message_attachment_file_object(
            message_id=77,
            owner_user_id=5,
            source_channel_type="app",
            source_provider_type="dcx_app",
            original_filename="offer.pdf",
            file_bytes=b"12345",
            content_type="application/pdf",
            build_r2_client=lambda: None,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_CONTACT_MESSAGE_ATTACHMENT_TOO_LARGE"
    else:
        raise AssertionError("Expected oversized attachment to raise")


def test_raises_when_attachment_type_is_unsupported(monkeypatch) -> None:
    monkeypatch.setenv("DCX_R2_APP_BUCKET_NAME", "dcx-app-bucket")

    try:
        store_dcx_contact_message_attachment_file_object(
            message_id=77,
            owner_user_id=5,
            source_channel_type="app",
            source_provider_type="dcx_app",
            original_filename="sheet.xlsx",
            file_bytes=b"spreadsheet",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            build_r2_client=lambda: None,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED"
    else:
        raise AssertionError("Expected unsupported attachment type to raise")
