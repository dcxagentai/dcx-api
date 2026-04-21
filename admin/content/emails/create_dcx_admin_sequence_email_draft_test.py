from admin.content.emails.create_dcx_admin_sequence_email_draft import (
    create_dcx_admin_sequence_email_draft_capability,
)


class _FakeCursor:
    def __init__(self, fetchone_results, fetchall_results):
        self._fetchone_results = list(fetchone_results)
        self._fetchall_results = list(fetchall_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        return None

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
        self._fetchone_results = fetchone_results
        self._fetchall_results = fetchall_results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._fetchone_results, self._fetchall_results)


def test_inserts_new_live_sequence_email_draft() -> None:
    result = create_dcx_admin_sequence_email_draft_capability(
        email_subject="Welcome to DCX",
        language_code="en",
        connect_to_database=lambda **_: _FakeConnection(
            fetchone_results=[(4,), (22,)],
            fetchall_results=[[]],
        ),
    )

    assert result == {
        "email_id": 22,
        "email_key": "welcome-to-dcx",
        "language_code": "en",
    }


def test_appends_numeric_suffix_when_sequence_email_key_already_used() -> None:
    result = create_dcx_admin_sequence_email_draft_capability(
        email_subject="Welcome to DCX",
        language_code="en",
        connect_to_database=lambda **_: _FakeConnection(
            fetchone_results=[(4,), (31,)],
            fetchall_results=[[("welcome-to-dcx",), ("welcome-to-dcx-2",)]],
        ),
    )

    assert result == {
        "email_id": 31,
        "email_key": "welcome-to-dcx-3",
        "language_code": "en",
    }


def test_raises_clear_error_for_blank_subject() -> None:
    try:
        create_dcx_admin_sequence_email_draft_capability(
            email_subject=" ",
            language_code="en",
            connect_to_database=lambda **_: _FakeConnection([], []),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_ADMIN_SEQUENCE_EMAIL_DRAFT_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected blank subject to raise a stable runtime error.")
