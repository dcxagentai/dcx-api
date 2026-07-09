from admin.translations.store_dcx_admin_ai_translation_result import (
    store_dcx_admin_ai_translation_result,
)


class _FakeCursor:
    def __init__(self, fetchone_results, fetchall_results):
        self._fetchone_results = list(fetchone_results)
        self._fetchall_results = list(fetchall_results)
        self.executed_queries = []

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


def test_stores_ai_translated_content_page_with_utf8_slug_and_conflict_suffix() -> None:
    fake_cursor = _FakeCursor(
        fetchone_results=[
            (101,),
            None,
            (301,),
        ],
        fetchall_results=[
            [
                ("سياسة-خصوصية-واتساب",),
                ("سياسة-خصوصية-واتساب-2",),
            ],
        ],
    )

    result = store_dcx_admin_ai_translation_result(
        cursor=fake_cursor,
        source_payload={
            "entity_kind": "content_page",
            "entity_key": "whatsapp-privacy-policy",
            "category_key": "policies",
            "source_row_id": 101,
            "stable_fields": {
                "page_slug": "whatsapp-privacy-policy",
            },
        },
        target_language={
            "language_id": 9,
            "language_code": "ar",
        },
        translated_fields={
            "page_title": "سياسة خصوصية واتساب",
            "page_lede": "نص تمهيدي",
            "page_body_markdown": "النص",
            "meta_title": "سياسة خصوصية واتساب",
            "meta_description": "وصف",
            "page_slug": "سياسة خصوصية واتساب",
        },
    )

    assert result["target_row_id"] == 301
    insert_query, insert_params = fake_cursor.executed_queries[-1]
    assert "INSERT INTO stephen_dcx_content_pages" in insert_query
    assert insert_params[8] == "سياسة-خصوصية-واتساب-3"
