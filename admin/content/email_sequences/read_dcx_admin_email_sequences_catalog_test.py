from admin.content.email_sequences.read_dcx_admin_email_sequences_catalog import (
    read_dcx_admin_email_sequences_catalog_capability,
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


def test_returns_sequence_catalog_rows_with_step_and_send_counts() -> None:
    fake_connection = _FakeConnection(
        fetchall_results=[
            [
                (
                    801,
                    "weekly-campaign",
                    "Weekly Campaign",
                    "campaign",
                    "all_email",
                    "manual_launch",
                    None,
                    False,
                    1777000000000,
                    1777000005000,
                    3,
                    2,
                    1,
                    1777100000000,
                )
            ]
        ]
    )

    payload = read_dcx_admin_email_sequences_catalog_capability(
        connect_to_database=lambda **_: fake_connection
    )

    assert payload == {
        "sequences": [
            {
                "sequence_id": 801,
                "sequence_key": "weekly-campaign",
                "sequence_name": "Weekly Campaign",
                "sequence_type": "campaign",
                "audience_type": "all_email",
                "trigger_type": "manual_launch",
                "scheduled_launch_at_ts_ms": None,
                "is_live": False,
                "created_at_ts_ms": 1777000000000,
                "updated_at_ts_ms": 1777000005000,
                "total_step_count": 3,
                "active_step_count": 2,
                "total_send_count": 1,
                "latest_send_at_ts_ms": 1777100000000,
            }
        ],
        "total_sequence_count": 1,
    }
