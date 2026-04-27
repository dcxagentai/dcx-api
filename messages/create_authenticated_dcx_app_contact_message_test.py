from unittest.mock import patch

from messages.create_authenticated_dcx_app_contact_message import (
    create_authenticated_dcx_app_contact_message,
)


class _FakeCursor:
    def __init__(self, fetchone_values, fetchall_values=None):
        self.fetchone_values = list(fetchone_values)
        self.fetchall_values = list(fetchall_values or [])
        self.executed_sql = []

    def execute(self, sql, params=None):
        self.executed_sql.append((" ".join(sql.split()), params))

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


class _ConnectFactory:
    def __init__(self, connections):
        self._connections = list(connections)

    def __call__(self, **_kwargs):
        return self._connections.pop(0)


def test_creates_ready_message_job_and_analysis_run_when_derivation_succeeds() -> None:
    first_connection = _FakeConnection(_FakeCursor([(77,), (7001,)]))
    second_connection = _FakeConnection(_FakeCursor([]))
    third_connection = _FakeConnection(
        _FakeCursor(
            [(7001, "app", "dcx_app", "text", "", "Hola, vendo trigo.", "queued", "pending", "pending"), None, (9001,)],
            [[]],
        )
    )
    fourth_connection = _FakeConnection(_FakeCursor([(4,)]))

    result = create_authenticated_dcx_app_contact_message(
        authenticated_user_id=77,
        message_text="Hola, vendo trigo.",
        connect_to_database=_ConnectFactory(
            [first_connection, second_connection, third_connection, fourth_connection]
        ),
        current_timestamp_ms_provider=lambda: 1777000000000,
        derive_message_with_llm=lambda _text: {
            "derived_text_content": "Hola, vendo trigo.",
            "analysis_summary_text": "The message says the user is selling wheat.",
            "detected_language_code": "de",
            "derivation_mode": "openai_responses_api",
            "model_name": "gpt-5.2",
        },
    )

    assert result == {
        "message_id": 7001,
        "job_id": 9001,
        "processing_status": "ready",
        "derivation_status": "completed",
    }
    assert any(
        "INSERT INTO stephen_dcx_contact_messages" in statement[0]
        for statement in first_connection.cursor_instance.executed_sql
    )
    assert any(
        "INSERT INTO stephen_dcx_contact_message_analysis_runs" in statement[0]
        for statement in fourth_connection.cursor_instance.executed_sql
    )


def test_creates_mixed_message_after_preparing_attachment_when_file_is_present() -> None:
    first_connection = _FakeConnection(_FakeCursor([(77,)]))
    second_connection = _FakeConnection(_FakeCursor([(77,), (7001,)]))
    third_connection = _FakeConnection(
        _FakeCursor(
            [(7001, "app", "dcx_app", "mixed", "", "See attached offer.", "queued", "pending", "pending"), None, (9001,)],
            [[]],
        )
    )
    fourth_connection = _FakeConnection(_FakeCursor([None]))
    event_order: list[str] = []
    prepared_attachment_calls: list[dict] = []

    result = create_authenticated_dcx_app_contact_message(
        authenticated_user_id=77,
        message_text="See attached offer.",
        attachment_inputs=[
            {
                "original_filename": "offer.pdf",
                "content_type": "application/pdf",
                "file_bytes": b"pdf-bytes",
            }
        ],
        connect_to_database=_ConnectFactory(
            [first_connection, second_connection, third_connection, fourth_connection]
        ),
        current_timestamp_ms_provider=lambda: 1777000000000,
        derive_message_with_llm=lambda _text: {
            "derived_text_content": "See attached offer.",
            "analysis_summary_text": "The user attached one offer document.",
            "detected_language_code": None,
            "derivation_mode": "fallback_no_model_configured",
            "model_name": "",
        },
        prepare_message_attachment=lambda **kwargs: event_order.append("prepare_attachment")
        or prepared_attachment_calls.append(kwargs)
        or {
            "file_uuid": "00000000-0000-0000-0000-000000000801",
            "file_kind": "document",
            "content_type": "application/pdf",
            "original_filename": "offer.pdf",
            "file_size_bytes": 9,
            "bucket_alias": "app",
            "object_key": "prepared-r2-key",
            "provider_media_id": None,
            "sort_order": 1,
            "stored_at_ts_ms": 1777000000000,
            "owner_user_id": 77,
            "source_channel_type": "app",
            "source_provider_type": "dcx_app",
        },
        persist_prepared_message_attachment=lambda **kwargs: event_order.append("persist_attachment")
        or {
            **kwargs["prepared_attachment"],
            "attachment_id": 81,
            "file_object_id": 91,
        },
    )

    assert result["message_id"] == 7001
    assert prepared_attachment_calls[0]["original_filename"] == "offer.pdf"
    assert event_order == ["prepare_attachment", "persist_attachment"]
    assert any(
        "UPDATE stephen_dcx_contact_messages SET message_format = %s" in statement[0]
        for statement in second_connection.cursor_instance.executed_sql
    )


def test_does_not_create_message_when_attachment_preparation_fails() -> None:
    first_connection = _FakeConnection(_FakeCursor([(77,)]))

    try:
        create_authenticated_dcx_app_contact_message(
            authenticated_user_id=77,
            message_text="See attached offer.",
            attachment_inputs=[
                {
                    "original_filename": "offer.pdf",
                    "content_type": "application/pdf",
                    "file_bytes": b"pdf-bytes",
                }
            ],
            connect_to_database=_ConnectFactory([first_connection]),
            current_timestamp_ms_provider=lambda: 1777000000000,
            prepare_message_attachment=lambda **_kwargs: (_ for _ in ()).throw(
                RuntimeError("API_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED")
            ),
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_CONTACT_MESSAGE_ATTACHMENT_UNSUPPORTED"
    else:
        raise AssertionError("Expected attachment preparation failure to raise")

    assert not any(
        "INSERT INTO stephen_dcx_contact_messages" in statement[0]
        for statement in first_connection.cursor_instance.executed_sql
    )


def test_raises_when_message_text_is_blank() -> None:
    try:
        create_authenticated_dcx_app_contact_message(
            authenticated_user_id=77,
            message_text="   ",
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_AUTHENTICATED_DCX_CONTACT_MESSAGE_TEXT_REQUIRED"
    else:
        raise AssertionError("Expected blank message text to raise")


def test_preserves_runtime_error_from_message_analysis_processing() -> None:
    first_connection = _FakeConnection(_FakeCursor([(77,), (7001,)]))
    second_connection = _FakeConnection(_FakeCursor([]))

    with patch(
        "messages.create_authenticated_dcx_app_contact_message.process_stored_dcx_contact_message_analysis",
        side_effect=RuntimeError("API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED"),
    ):
        try:
            create_authenticated_dcx_app_contact_message(
                authenticated_user_id=77,
                message_text="Hola, vendo trigo.",
                connect_to_database=_ConnectFactory([first_connection, second_connection]),
                current_timestamp_ms_provider=lambda: 1777000000000,
            )
        except RuntimeError as runtime_error:
            assert str(runtime_error) == "API_DCX_CONTACT_MESSAGE_ANALYSIS_PROCESS_FAILED"
        else:
            raise AssertionError("Expected analysis processing failure to raise")
