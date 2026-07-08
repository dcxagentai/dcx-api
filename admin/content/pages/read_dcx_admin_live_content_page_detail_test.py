from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from admin.content.pages.read_dcx_admin_live_content_page_detail import (
    read_dcx_admin_live_content_page_detail_capability,
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


def test_returns_requested_live_content_page_detail_with_ai_metadata() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                101,
                "test-page",
                "insights",
                "Test Page",
                "Lede",
                "Body",
                "Meta title",
                "Meta description",
                "test-page",
                "draft",
                None,
                True,
                True,
                None,
                None,
                1778000000000,
                1778001000000,
                1,
                "en",
                "English",
                "English",
                False,
                20,
                "Insights",
                "Insight pages",
                "insights",
                None,
                None,
                None,
                None,
            ),
            ("Test Page", "Lede", "Body", "Meta title", "Meta description"),
        ],
        fetchall_results=[
            [
                (1, "en", "English", "English", False),
                (2, "es", "Spanish", "Espanol", False),
            ],
            [
                (
                    101,
                    "test-page",
                    "Test Page",
                    "test-page",
                    "draft",
                    True,
                    1778000000000,
                    1778001000000,
                    1,
                    "en",
                    "English",
                    "English",
                    False,
                    None,
                    None,
                    None,
                    None,
                    "insights",
                ),
            ],
        ],
    )

    payload = read_dcx_admin_live_content_page_detail_capability(
        page_key="test-page",
        language_code="en",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload["page_id"] == 101
    assert payload["page_key"] == "test-page"
    assert payload["language"]["language_code"] == "en"
    assert payload["category"]["category_name"] == "Insights"
    assert payload["ai_translation"] == {
        "is_ai_translated": False,
        "is_stale": False,
        "job_id": None,
        "source_row_id_snapshot": None,
        "translated_at_ts_ms": None,
    }
    assert payload["translation_summary"]["existing_translations"][0]["category_slug"] == "insights"
    assert (
        payload["translation_summary"]["existing_translations"][0]["public_route_path"]
        == "/en/insights/test-page"
    )
    assert payload["translation_summary"]["missing_languages"][0]["language_code"] == "es"


def test_raises_clear_error_when_live_content_page_detail_missing() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[None, None],
        fetchall_results=[[], []],
    )

    try:
        read_dcx_admin_live_content_page_detail_capability(
            page_key="missing",
            language_code="en",
            connect_to_database=lambda **_: fake_connection,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_CONTENT_PAGE_DETAIL_NOT_FOUND"
    else:
        raise AssertionError("Expected missing content page detail to fail.")
