from admin.content.email_sequences.create_dcx_admin_email_sequence_draft import (
    create_dcx_admin_email_sequence_draft_capability,
)


class _FakeCursor:
    def __init__(self, fetchone_results, fetchall_results):
        self._fetchone_results = list(fetchone_results)
        self._fetchall_results = list(fetchall_results)
        self.executed_queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed_queries.append((query, params))

    def fetchone(self):
        if not self._fetchone_results:
            return None
        return self._fetchone_results.pop(0)

    def fetchall(self):
        if not self._fetchall_results:
            return []
        return self._fetchall_results.pop(0)


class _FakeConnection:
    def __init__(self, fetchone_results, fetchall_results):
        self.cursor_instance = _FakeCursor(fetchone_results, fetchall_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


def test_inserts_new_email_sequence_draft() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[(701,)],
        fetchall_results=[[("weekly-campaign",)]],
    )

    payload = create_dcx_admin_email_sequence_draft_capability(
        authenticated_admin_user_id=7,
        sequence_name="Weekly Campaign",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "sequence_id": 701,
        "sequence_key": "weekly-campaign-2",
    }


def test_appends_numeric_suffix_when_sequence_key_already_used() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[(702,)],
        fetchall_results=[[("weekly-campaign",), ("weekly-campaign-2",)]],
    )

    payload = create_dcx_admin_email_sequence_draft_capability(
        authenticated_admin_user_id=7,
        sequence_name="Weekly Campaign",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload["sequence_key"] == "weekly-campaign-3"


def test_raises_clear_error_for_blank_sequence_name() -> None:
    try:
        create_dcx_admin_email_sequence_draft_capability(
            authenticated_admin_user_id=7,
            sequence_name=" ",
            connect_to_database=lambda **_: None,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_EMAIL_SEQUENCE_DRAFT_INVALID"
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected blank sequence name to fail.")
