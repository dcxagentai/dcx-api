from admin.content.pages.create_dcx_admin_content_page_translation import (
    create_dcx_admin_content_page_translation_capability,
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


def test_creates_translation_row_from_source_page() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (101, "weekly-page", "insights", "Weekly Page", "Lede", "Body", "Meta", "Desc", "weekly-page", "draft", None),
            (3,),
            None,
            (101,),
            (401,),
        ]
    )

    payload = create_dcx_admin_content_page_translation_capability(
        page_key="weekly-page",
        source_language_code="en",
        target_language_code="fr",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "page_id": 401,
        "page_key": "weekly-page",
        "language_code": "fr",
    }


def test_raises_clear_error_when_translation_already_exists() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (101, "weekly-page", "insights", "Weekly Page", "Lede", "Body", "Meta", "Desc", "weekly-page", "draft", None),
            (3,),
            (301,),
        ]
    )

    try:
        create_dcx_admin_content_page_translation_capability(
            page_key="weekly-page",
            source_language_code="en",
            target_language_code="fr",
            connect_to_database=lambda **_: fake_connection,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_CONTENT_PAGE_TRANSLATION_ALREADY_EXISTS"
    else:  # pragma: no cover
        raise AssertionError("Expected translation create to fail when the target row already exists.")
