from messages.read_authenticated_dcx_user_contact_message_attachment_stream import (
    read_authenticated_dcx_user_contact_message_attachment_stream,
)


class _FakeBody:
    def __init__(self, content: bytes):
        self.content = content

    def read(self):
        return self.content


class _FakeR2Client:
    def __init__(self, content: bytes):
        self.content = content

    def get_object(self, **_kwargs):
        return {"Body": _FakeBody(self.content)}


class _FakeCursor:
    def __init__(self, fetchone_values):
        self.fetchone_values = list(fetchone_values)

    def execute(self, _sql, _params=None):
        return None

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


def test_returns_attachment_stream_when_attachment_belongs_to_user(monkeypatch) -> None:
    monkeypatch.setenv("DCX_R2_APP_BUCKET_NAME", "dcx-app-bucket")

    result = read_authenticated_dcx_user_contact_message_attachment_stream(
        authenticated_user_id=7,
        message_id=33,
        attachment_id=99,
        connect_to_database=lambda **_kwargs: _FakeConnection(
            _FakeCursor([("app", "messages/33/test.png", "image/png", "test.png", "image", {})])
        ),
        build_r2_client=lambda: _FakeR2Client(b"image-bytes"),
    )

    assert result == {
        "content_bytes": b"image-bytes",
        "content_type": "image/png",
        "original_filename": "test.png",
        "file_kind": "image",
    }


def test_returns_none_when_attachment_is_missing() -> None:
    result = read_authenticated_dcx_user_contact_message_attachment_stream(
        authenticated_user_id=7,
        message_id=33,
        attachment_id=99,
        connect_to_database=lambda **_kwargs: _FakeConnection(_FakeCursor([None])),
        build_r2_client=lambda: _FakeR2Client(b"unused"),
    )

    assert result is None


def test_returns_none_when_parent_message_is_prohibited() -> None:
    result = read_authenticated_dcx_user_contact_message_attachment_stream(
        authenticated_user_id=7,
        message_id=33,
        attachment_id=99,
        connect_to_database=lambda **_kwargs: _FakeConnection(
            _FakeCursor(
                [
                    (
                        "app",
                        "messages/33/test.png",
                        "image/png",
                        "test.png",
                        "image",
                        {"moderation_status": "prohibited"},
                    )
                ]
            )
        ),
        build_r2_client=lambda: _FakeR2Client(b"unused"),
    )

    assert result is None
