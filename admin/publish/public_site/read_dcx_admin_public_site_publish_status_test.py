from admin.publish.public_site.read_dcx_admin_public_site_publish_status import (
    read_dcx_admin_public_site_publish_status_capability,
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
        self._fetchone_results = fetchone_results
        self._fetchall_results = fetchall_results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._fetchone_results, self._fetchall_results)


def test_returns_publish_status_with_pending_change_count_and_preview() -> None:
    result = read_dcx_admin_public_site_publish_status_capability(
        connect_to_database=lambda **_: _FakeConnection(
            fetchone_results=[
                (
                    1,
                    "dcx_public",
                    1770000000000,
                    5,
                    1770000005000,
                    5,
                    "trigger_accepted",
                    "Cloudflare Pages deploy hook accepted the publish request.",
                    1769000000000,
                    1770000005000,
                ),
                (3,),
                (1,),
            ],
            fetchall_results=[
                [
                    (301, "home", "meta_title", "es", "Español", 1770000100000),
                    (302, "signup_form", "submit_button_label", "fr", "Français", 1770000200000),
                ],
                [
                    (
                        401,
                        "Market wrap for April",
                        "insights",
                        "market-wrap-april",
                        "en",
                        "English",
                        1770000300000,
                    ),
                ]
            ],
        ),
    )

    assert result["surface_key"] == "dcx_public"
    assert result["runtime_environment"] in {"local", "development", "production"}
    assert result["publish_execution_mode"] in {"local_manual_rebuild", "cloudflare_pages_hook"}
    assert result["pending_change_count"] == 4
    assert result["pending_changes_preview"] == [
        {
            "content_kind": "content_page",
            "item_id": 401,
            "primary_label": "Market wrap for April",
            "secondary_label": "insights / market-wrap-april",
            "public_path": "/en/insights/market-wrap-april",
            "language_code": "en",
            "language_name_native": "English",
            "updated_at_ts_ms": 1770000300000,
        },
        {
            "content_kind": "ux_string",
            "item_id": 302,
            "primary_label": "signup_form / submit_button_label",
            "secondary_label": None,
            "public_path": None,
            "language_code": "fr",
            "language_name_native": "Français",
            "updated_at_ts_ms": 1770000200000,
        },
        {
            "content_kind": "ux_string",
            "item_id": 301,
            "primary_label": "home / meta_title",
            "secondary_label": None,
            "public_path": None,
            "language_code": "es",
            "language_name_native": "Español",
            "updated_at_ts_ms": 1770000100000,
        },
    ]
    assert result["public_managed_content_kinds"] == ["ux_strings", "content_pages"]


def test_returns_zero_pending_changes_when_last_successful_publish_is_current() -> None:
    result = read_dcx_admin_public_site_publish_status_capability(
        connect_to_database=lambda **_: _FakeConnection(
            fetchone_results=[
                (
                    1,
                    "dcx_public",
                    1770000300000,
                    5,
                    1770000300000,
                    5,
                    "trigger_accepted",
                    "Cloudflare Pages deploy hook accepted the publish request.",
                    1769000000000,
                    1770000300000,
                ),
                (0,),
                (0,),
            ],
            fetchall_results=[[], []],
        ),
    )

    assert result["pending_change_count"] == 0
    assert result["pending_changes_preview"] == []
