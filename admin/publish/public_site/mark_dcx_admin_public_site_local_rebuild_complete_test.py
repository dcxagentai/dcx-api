from unittest.mock import patch

from admin.publish.public_site.mark_dcx_admin_public_site_local_rebuild_complete import (
    mark_dcx_admin_public_site_local_rebuild_complete_capability,
)


class _FakeCursor:
    def __init__(self):
        self.executed_queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed_queries.append((query, params))


class _FakeConnection:
    def __init__(self):
        self.cursors = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        cursor = _FakeCursor()
        self.cursors.append(cursor)
        return cursor


def test_records_local_rebuild_completion_when_runtime_is_local() -> None:
    fake_connections = []

    def connect_to_database(**_):
        connection = _FakeConnection()
        fake_connections.append(connection)
        return connection

    with patch.dict("os.environ", {"DCX_ENVIRONMENT": "development"}, clear=False):
        result = mark_dcx_admin_public_site_local_rebuild_complete_capability(
            completed_by_user_id=5,
            connect_to_database=connect_to_database,
            current_timestamp_ms=lambda: 1770000000000,
        )

    assert result == {
        "surface_key": "dcx_public",
        "completed_by_user_id": 5,
        "completed_at_ts_ms": 1770000000000,
        "last_publish_status": "local_manual_rebuild_completed",
        "last_publish_message": "Local public rebuild marked complete after manual dcx_public refresh.",
    }
    assert len(fake_connections) == 1


def test_raises_clear_error_when_called_outside_local_runtime() -> None:
    with patch.dict("os.environ", {"DCX_ENVIRONMENT": "production"}, clear=False):
        try:
            mark_dcx_admin_public_site_local_rebuild_complete_capability(
                completed_by_user_id=5,
                connect_to_database=lambda **_: _FakeConnection(),
                current_timestamp_ms=lambda: 1770000000000,
            )
        except RuntimeError as exc:
            assert str(exc) == "API_DCX_ADMIN_PUBLIC_SITE_LOCAL_REBUILD_COMPLETE_FORBIDDEN"
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected hosted runtime call to local rebuild completion to fail.")
