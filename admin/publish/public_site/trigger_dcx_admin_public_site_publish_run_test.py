from unittest.mock import patch

from admin.publish.public_site.trigger_dcx_admin_public_site_publish_run import (
    trigger_dcx_admin_public_site_publish_run_capability,
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


def test_returns_trigger_accepted_result_when_hook_post_succeeds() -> None:
    fake_connections = []

    def connect_to_database(**_):
        connection = _FakeConnection()
        fake_connections.append(connection)
        return connection

    class _SuccessResponse:
        status_code = 201

    with patch.dict(
        "os.environ",
        {
            "DCX_PUBLIC_CLOUDFLARE_PAGES_DEPLOY_HOOK_URL": "https://example.com/hook",
            "DCX_ENVIRONMENT": "production",
        },
        clear=False,
    ):
        result = trigger_dcx_admin_public_site_publish_run_capability(
            triggered_by_user_id=5,
            connect_to_database=connect_to_database,
            post_to_deploy_hook=lambda *_, **__: _SuccessResponse(),
            current_timestamp_ms=lambda: 1770000000000,
        )

    assert result == {
        "surface_key": "dcx_public",
        "triggered_by_user_id": 5,
        "accepted_publish_at_ts_ms": 1770000000000,
        "last_publish_status": "trigger_accepted",
        "last_publish_message": "Cloudflare Pages deploy hook accepted the publish request.",
    }
    assert len(fake_connections) == 2


def test_returns_local_manual_rebuild_result_in_local_development() -> None:
    fake_connections = []

    def connect_to_database(**_):
        connection = _FakeConnection()
        fake_connections.append(connection)
        return connection

    with patch.dict(
        "os.environ",
        {"DCX_ENVIRONMENT": "development"},
        clear=False,
    ):
        result = trigger_dcx_admin_public_site_publish_run_capability(
            triggered_by_user_id=5,
            connect_to_database=connect_to_database,
            current_timestamp_ms=lambda: 1770000000000,
        )

    assert result == {
        "surface_key": "dcx_public",
        "triggered_by_user_id": 5,
        "accepted_publish_at_ts_ms": 1770000000000,
        "last_publish_status": "local_manual_rebuild_required",
        "last_publish_message": "Local mode does not call Cloudflare. Run npm run dev or npm run build in dcx_public against the local API to refresh the public site.",
    }
    assert len(fake_connections) == 2


def test_raises_clear_error_when_deploy_hook_url_is_missing() -> None:
    with patch.dict(
        "os.environ",
        {
            "DCX_PUBLIC_CLOUDFLARE_PAGES_DEPLOY_HOOK_URL": "",
            "DCX_ENVIRONMENT": "production",
        },
        clear=False,
    ):
        try:
            trigger_dcx_admin_public_site_publish_run_capability(
                triggered_by_user_id=5,
                connect_to_database=lambda **_: _FakeConnection(),
                current_timestamp_ms=lambda: 1770000000000,
            )
        except RuntimeError as exc:
            assert str(exc) == "API_DCX_ADMIN_PUBLIC_SITE_DEPLOY_HOOK_NOT_CONFIGURED"
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected missing deploy hook URL to raise a stable runtime error.")


def test_raises_clear_error_when_hook_post_fails() -> None:
    fake_connections = []

    def connect_to_database(**_):
        connection = _FakeConnection()
        fake_connections.append(connection)
        return connection

    with patch.dict(
        "os.environ",
        {
            "DCX_PUBLIC_CLOUDFLARE_PAGES_DEPLOY_HOOK_URL": "https://example.com/hook",
            "DCX_ENVIRONMENT": "production",
        },
        clear=False,
    ):
        try:
            trigger_dcx_admin_public_site_publish_run_capability(
                triggered_by_user_id=5,
                connect_to_database=connect_to_database,
                post_to_deploy_hook=lambda *_, **__: (_ for _ in ()).throw(RuntimeError("network down")),
                current_timestamp_ms=lambda: 1770000000000,
            )
        except RuntimeError as exc:
            assert str(exc) == "API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_TRIGGER_FAILED"
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected failing deploy hook post to raise a stable runtime error.")

    assert len(fake_connections) == 2
