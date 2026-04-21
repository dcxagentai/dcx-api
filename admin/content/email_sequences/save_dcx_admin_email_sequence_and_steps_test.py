from admin.content.email_sequences.save_dcx_admin_email_sequence_and_steps import (
    save_dcx_admin_email_sequence_and_steps_capability,
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


def test_updates_sequence_metadata_and_replaces_steps() -> None:
    fake_connection = _FakeConnection(fetchone_results=[(821,)], fetchall_results=[[(101,), (102,)]])

    payload = save_dcx_admin_email_sequence_and_steps_capability(
        authenticated_admin_user_id=7,
        sequence_key="weekly-campaign",
        sequence_name="Weekly Campaign",
        sequence_type="campaign",
        audience_type="all_email",
        trigger_type="manual_launch",
        scheduled_launch_at_ts_ms=None,
        is_live=True,
        steps=[
            {
                "step_name": "Welcome step",
                "source_email_id": 101,
                "delay_minutes_from_trigger": 0,
                "is_active": True,
            },
            {
                "step_name": "Follow-up step",
                "source_email_id": 102,
                "delay_minutes_from_trigger": 1440,
                "is_active": True,
            },
        ],
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "sequence_id": 821,
        "sequence_key": "weekly-campaign",
        "saved_step_count": 2,
    }
    assert "DELETE FROM stephen_dcx_emails_sequence_steps" in fake_connection.cursor_instance.executed_queries[4][0]
    assert fake_connection.cursor_instance.executed_queries[5][1][1] == "welcome-step"
    assert fake_connection.cursor_instance.executed_queries[6][1][1] == "follow-up-step"


def test_raises_clear_error_when_sequence_missing() -> None:
    fake_connection = _FakeConnection(fetchone_results=[None], fetchall_results=[])

    try:
        save_dcx_admin_email_sequence_and_steps_capability(
            authenticated_admin_user_id=7,
            sequence_key="missing-sequence",
            sequence_name="Missing Sequence",
            sequence_type="campaign",
            audience_type="all_email",
            trigger_type="manual_launch",
            scheduled_launch_at_ts_ms=None,
            is_live=False,
            steps=[],
            connect_to_database=lambda **_: fake_connection,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_NOT_FOUND"
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected missing sequence save to fail.")


def test_raises_clear_error_for_invalid_sequence_payload() -> None:
    try:
        save_dcx_admin_email_sequence_and_steps_capability(
            authenticated_admin_user_id=7,
            sequence_key="weekly-campaign",
            sequence_name="Weekly Campaign",
            sequence_type="campaign",
            audience_type="all_email",
            trigger_type="scheduled_launch",
            scheduled_launch_at_ts_ms=None,
            is_live=False,
            steps=[],
            connect_to_database=lambda **_: None,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID"
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected invalid sequence payload to fail.")


def test_raises_clear_error_when_step_source_email_is_not_one_live_original_sequence_email() -> None:
    fake_connection = _FakeConnection(fetchone_results=[(821,)], fetchall_results=[[(101,)]] )

    try:
        save_dcx_admin_email_sequence_and_steps_capability(
            authenticated_admin_user_id=7,
            sequence_key="weekly-campaign",
            sequence_name="Weekly Campaign",
            sequence_type="campaign",
            audience_type="all_email",
            trigger_type="manual_launch",
            scheduled_launch_at_ts_ms=None,
            is_live=True,
            steps=[
                {
                    "step_name": "Welcome step",
                    "source_email_id": 101,
                    "delay_minutes_from_trigger": 0,
                    "is_active": True,
                },
                {
                    "step_name": "Follow-up step",
                    "source_email_id": 202,
                    "delay_minutes_from_trigger": 1440,
                    "is_active": True,
                },
            ],
            connect_to_database=lambda **_: fake_connection,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID"
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected invalid sequence source email ids to fail.")
