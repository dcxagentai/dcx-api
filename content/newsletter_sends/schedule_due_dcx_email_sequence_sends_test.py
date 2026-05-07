from content.newsletter_sends.schedule_due_dcx_email_sequence_sends import (
    schedule_due_dcx_email_sequence_sends_capability,
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


def test_schedules_due_sequence_with_role_scoped_audience() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (801, "shareholder-campaign", "shareholders", 1777100000000),
            (901,),
            (1001,),
        ],
        fetchall_results=[
            [
                (701, "welcome", 1, 301, 0, "shareholder-email", "Hello shareholders", "Plain body"),
            ],
            [
                (42, "shareholder@example.com", "all_email", "shareholder"),
            ],
        ],
    )

    payload = schedule_due_dcx_email_sequence_sends_capability(
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1777100000000,
        tracking_token_provider=lambda: "tracking-token",
    )

    assert payload == {
        "status": "scheduled",
        "scheduled_sequence": {
            "sequence_id": 801,
            "sequence_key": "shareholder-campaign",
            "send_count": 1,
            "recipient_count": 1,
        },
    }
    assert "trigger_type = 'scheduled_launch'" in fake_connection.cursor_instance.executed_queries[0][0]
    assert fake_connection.cursor_instance.executed_queries[2][1] == (
        "shareholders",
        "shareholders",
        "shareholders",
        "shareholders",
    )
    assert "'scheduled', 'newsletters'" in fake_connection.cursor_instance.executed_queries[4][0]
    assert fake_connection.cursor_instance.executed_queries[4][1][4] == 1777100000000
    assert fake_connection.cursor_instance.executed_queries[5][1][4] == "all_email"
    assert "trigger_type = 'manual_launch'" in fake_connection.cursor_instance.executed_queries[7][0]
    assert "scheduled_launch_at_ts_ms = NULL" in fake_connection.cursor_instance.executed_queries[7][0]


def test_due_sequence_with_no_active_steps_is_consumed_without_invalid_schedule_state() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (802, "empty-campaign", "devs", 1777100000000),
        ],
        fetchall_results=[
            [],
        ],
    )

    payload = schedule_due_dcx_email_sequence_sends_capability(
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1777100000000,
        tracking_token_provider=lambda: "tracking-token",
    )

    assert payload == {
        "status": "scheduled",
        "scheduled_sequence": {"sequence_id": 802, "send_count": 0},
    }
    assert "trigger_type = 'manual_launch'" in fake_connection.cursor_instance.executed_queries[2][0]
    assert "scheduled_launch_at_ts_ms = NULL" in fake_connection.cursor_instance.executed_queries[2][0]
