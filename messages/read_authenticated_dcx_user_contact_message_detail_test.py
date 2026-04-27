from messages.read_authenticated_dcx_user_contact_message_detail import (
    read_authenticated_dcx_user_contact_message_detail,
)


class _FakeCursor:
    def __init__(self, fetchone_values, fetchall_values):
        self.fetchone_values = list(fetchone_values)
        self.fetchall_values = list(fetchall_values)

    def execute(self, _sql, _params=None):
        return None

    def fetchone(self):
        if not self.fetchone_values:
            return None
        return self.fetchone_values.pop(0)

    def fetchall(self):
        if not self.fetchall_values:
            return []
        return self.fetchall_values.pop(0)

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


def test_returns_message_detail_when_visible_message_belongs_to_user() -> None:
    result = read_authenticated_dcx_user_contact_message_detail(
        authenticated_user_id=77,
        message_id=901,
        connect_to_database=lambda **_kwargs: _FakeConnection(
            _FakeCursor(
                [
                    (
                        901,
                        "app",
                        "dcx_app",
                        "inbound",
                        "text",
                        "",
                        "Hola",
                        "Hola",
                        "Greeting in Spanish.",
                        "ready",
                        "completed",
                        "completed",
                        "gemini-test",
                        {},
                        1777000004000,
                        "es",
                        1777000000000,
                        1777000000000,
                        1777000005000,
                    )
                ],
                [[]],
            )
        ),
    )

    assert result is not None
    assert result["message_id"] == 901
    assert result["attachments"] == []


def test_returns_message_detail_attachment_url_path_by_file_uuid() -> None:
    result = read_authenticated_dcx_user_contact_message_detail(
        authenticated_user_id=77,
        message_id=901,
        connect_to_database=lambda **_kwargs: _FakeConnection(
            _FakeCursor(
                [
                    (
                        901,
                        "whatsapp",
                        "meta_whatsapp",
                        "inbound",
                        "image",
                        "",
                        "Photo caption",
                        "Photo caption",
                        "Stored raw text directly.",
                        "ready",
                        "completed",
                        "completed",
                        "gemini-test",
                        {},
                        1777000004000,
                        "en",
                        1777000000000,
                        1777000000000,
                        1777000005000,
                    )
                ],
                [
                    [
                        (
                            71,
                            81,
                            "primary_media",
                            "meta-media-123",
                            1,
                            "00000000-0000-0000-0000-000000000801",
                            "image",
                            "image/jpeg",
                            12345,
                            "whatsapp-image.jpg",
                            "completed",
                            "Trade photo summary.",
                            "A trade photo.",
                            "",
                            "Photo shows a trade offer.",
                            "Image attached to the caption.",
                            "gemini-test",
                            {},
                            1777000004000,
                            "en",
                        )
                    ]
                ],
            )
        ),
    )

    assert result is not None
    assert result["attachments"][0]["file_uuid"] == "00000000-0000-0000-0000-000000000801"
    assert result["attachments"][0]["analysis_summary_text"] == "Trade photo summary."
    assert result["attachments"][0]["attachment_url_path"] == "/users/me/messages/901/attachments/71/file"


def test_returns_message_detail_attachment_compatibility_url_when_file_uuid_missing() -> None:
    result = read_authenticated_dcx_user_contact_message_detail(
        authenticated_user_id=77,
        message_id=901,
        connect_to_database=lambda **_kwargs: _FakeConnection(
            _FakeCursor(
                [
                    (
                        901,
                        "whatsapp",
                        "meta_whatsapp",
                        "inbound",
                        "image",
                        "",
                        "Photo caption",
                        "Photo caption",
                        "Stored raw text directly.",
                        "ready",
                        "completed",
                        "completed",
                        "gemini-test",
                        {},
                        1777000004000,
                        "en",
                        1777000000000,
                        1777000000000,
                        1777000005000,
                    )
                ],
                [
                    [
                        (
                            71,
                            81,
                            "primary_media",
                            "meta-media-123",
                            1,
                            None,
                            "image",
                            "image/jpeg",
                            12345,
                            "whatsapp-image.jpg",
                            "completed",
                            "Trade photo summary.",
                            "A trade photo.",
                            "",
                            "Photo shows a trade offer.",
                            "Image attached to the caption.",
                            "gemini-test",
                            {},
                            1777000004000,
                            "en",
                        )
                    ]
                ],
            )
        ),
    )

    assert result is not None
    assert result["attachments"][0]["file_uuid"] is None
    assert result["attachments"][0]["attachment_url_path"] == "/users/me/messages/901/attachments/71/file"


def test_returns_none_when_message_is_missing() -> None:
    result = read_authenticated_dcx_user_contact_message_detail(
        authenticated_user_id=77,
        message_id=901,
        connect_to_database=lambda **_kwargs: _FakeConnection(_FakeCursor([None], [])),
    )

    assert result is None
