from admin.operations.read_dcx_admin_schedule_operations_catalog import (
    read_dcx_admin_schedule_operations_catalog_capability,
)


class _FakeCursor:
    def __init__(self, fetchall_results):
        self._fetchall_results = list(fetchall_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed_query = (query, params)

    def fetchall(self):
        if not self._fetchall_results:
            return []
        return self._fetchall_results.pop(0)


class _FakeConnection:
    def __init__(self, fetchall_results):
        self.cursor_instance = _FakeCursor(fetchall_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


def test_returns_newsletter_and_sequence_schedule_rows() -> None:
    fake_connection = _FakeConnection(
        fetchall_results=[
            [
                ("newsletter_send", "901", "weekly-alpha", "weekly-alpha", 1777000000000, "scheduled", "admins", "newsletter"),
                ("sequence_launch", "801", "weekly-campaign", "Weekly Campaign", 1777100000000, "scheduled", "all_email", "sequence"),
            ]
        ]
    )

    payload = read_dcx_admin_schedule_operations_catalog_capability(
        connect_to_database=lambda **_: fake_connection
    )

    assert payload == {
        "operations": [
            {
                "operation_kind": "newsletter_send",
                "operation_id": "901",
                "operation_key": "weekly-alpha",
                "title": "weekly-alpha",
                "scheduled_at_ts_ms": 1777000000000,
                "status": "scheduled",
                "audience_scope": "admins",
                "source_surface": "newsletter",
            },
            {
                "operation_kind": "sequence_launch",
                "operation_id": "801",
                "operation_key": "weekly-campaign",
                "title": "Weekly Campaign",
                "scheduled_at_ts_ms": 1777100000000,
                "status": "scheduled",
                "audience_scope": "all_email",
                "source_surface": "sequence",
            },
        ],
        "total_operation_count": 2,
    }
