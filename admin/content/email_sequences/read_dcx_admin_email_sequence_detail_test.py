from admin.content.email_sequences.read_dcx_admin_email_sequence_detail import (
    read_dcx_admin_email_sequence_detail_capability,
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
        self.executed_query = (query, params)

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


def test_returns_sequence_detail_with_ordered_steps() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                811,
                "weekly-campaign",
                "Weekly Campaign",
                "campaign",
                "all_email",
                "manual_launch",
                None,
                False,
                7,
                7,
                1777000000000,
                1777000005000,
            )
        ],
        fetchall_results=[
            [
                (
                    901,
                    "welcome-email",
                    "Welcome email",
                    1,
                    101,
                    0,
                    True,
                    1777000000000,
                    1777000005000,
                    "welcome-email",
                    "Welcome email",
                    "transactional",
                    "en",
                )
            ]
        ],
    )

    payload = read_dcx_admin_email_sequence_detail_capability(
        sequence_key="weekly-campaign",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload["sequence_key"] == "weekly-campaign"
    assert payload["steps"][0]["source_email_key"] == "welcome-email"
    assert payload["steps"][0]["step_order"] == 1


def test_raises_clear_error_when_sequence_missing() -> None:
    fake_connection = _FakeConnection(fetchone_results=[None], fetchall_results=[])

    try:
        read_dcx_admin_email_sequence_detail_capability(
            sequence_key="missing-sequence",
            connect_to_database=lambda **_: fake_connection,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_EMAIL_SEQUENCE_DETAIL_NOT_FOUND"
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected missing sequence lookup to fail.")
