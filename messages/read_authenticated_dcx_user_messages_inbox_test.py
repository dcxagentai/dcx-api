from messages.read_authenticated_dcx_user_messages_inbox import (
    read_authenticated_dcx_user_messages_inbox,
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


def test_returns_filtered_visible_messages_for_authenticated_user() -> None:
    result = read_authenticated_dcx_user_messages_inbox(
        authenticated_user_id=77,
        message_format_filter="text",
        connect_to_database=lambda **_kwargs: _FakeConnection(
            _FakeCursor(
                fetchone_values=[(77,)],
                fetchall_values=[
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
                            "es",
                            1777000000000,
                            1777000000000,
                            55,
                            "email",
                            "trader@example.com",
                            "trader@example.com",
                            "Main email",
                            "trader@example.com",
                            "chat@mail.dcxagent.ai",
                            [
                                {
                                    "attachment_id": 71,
                                    "file_kind": "document",
                                    "original_filename": "contract.pdf",
                                    "analysis_summary_text": "Contract outline for the next wheat shipment.",
                                }
                            ],
                        )
                    ]
                ],
            )
        ),
    )

    assert result["selected_filter"] == "text"
    assert result["total_message_count"] == 1
    assert result["messages"][0]["message_id"] == 901
    assert result["messages"][0]["detected_language_code"] == "es"
    assert result["messages"][0]["contact_method"] == {
        "id": 55,
        "contact_type": "email",
        "contact_value": "trader@example.com",
        "normalized_value": "trader@example.com",
        "display_label": "Main email",
    }
    assert result["messages"][0]["attachment_summaries"] == [
        {
            "attachment_id": 71,
            "file_kind": "document",
            "original_filename": "contract.pdf",
            "analysis_summary_text": "Contract outline for the next wheat shipment.",
        }
    ]


def test_raises_when_message_format_filter_is_invalid() -> None:
    try:
        read_authenticated_dcx_user_messages_inbox(
            authenticated_user_id=77,
            message_format_filter="video",
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_AUTHENTICATED_DCX_USER_MESSAGES_FILTER_INVALID"
    else:
        raise AssertionError("Expected invalid message filter to raise")
