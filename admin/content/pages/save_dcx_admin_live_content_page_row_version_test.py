from admin.content.pages.save_dcx_admin_live_content_page_row_version import (
    save_dcx_admin_live_content_page_row_version_capability,
)


class _FakeCursor:
    def __init__(self, fetchone_results):
        self._fetchone_results = list(fetchone_results)
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


class _FakeConnection:
    def __init__(self, fetchone_results):
        self.cursor_instance = _FakeCursor(fetchone_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


def test_saves_translated_page_when_only_original_category_row_exists() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                202,
                "live-test-page",
                "insights",
                2,
                "Live Test Page",
                "English lede",
                "English body",
                "English meta",
                "English description",
                "live-test-page",
                "draft",
                None,
                False,
                101,
            ),
            (1,),
            None,
            (303,),
        ]
    )

    payload = save_dcx_admin_live_content_page_row_version_capability(
        target_page_id=202,
        next_category_key="insights",
        next_page_title="Pagina de Prueba",
        next_page_lede="Esta es la página de prueba.",
        next_page_body_markdown="Cuerpo traducido",
        next_meta_title="Meta traducida",
        next_meta_description="Descripción traducida",
        next_page_slug="pagina-de-prueba",
        next_publication_status="draft",
        next_published_at_ts_ms=None,
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "page_id": 303,
        "previous_page_id": 202,
        "was_noop": False,
    }
    category_query, category_params = fake_connection.cursor_instance.executed_queries[1]
    assert "OR is_original = TRUE" in category_query
    assert category_params == ("insights", 2, 2)
