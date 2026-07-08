from admin.content.pages.publish_dcx_admin_content_page_translated_drafts import (
    publish_dcx_admin_content_page_translated_drafts_capability,
)


class _FakeCursor:
    def __init__(self, fetchall_results, fetchone_results):
        self._fetchall_results = list(fetchall_results)
        self._fetchone_results = list(fetchone_results)
        self.executed_queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed_queries.append((query, params))

    def fetchall(self):
        if not self._fetchall_results:
            return []
        return self._fetchall_results.pop(0)

    def fetchone(self):
        if not self._fetchone_results:
            return None
        return self._fetchone_results.pop(0)


class _FakeConnection:
    def __init__(self, fetchall_results, fetchone_results):
        self.cursor_instance = _FakeCursor(fetchall_results, fetchone_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


def test_publishes_existing_translated_draft_rows() -> None:
    fake_connection = _FakeConnection(
        fetchall_results=[
            [
                (
                    201,
                    "whatsapp-privacy-policy",
                    "policies",
                    2,
                    "Politica de privacidad",
                    "Lede ES",
                    "Body ES",
                    "Meta ES",
                    "Description ES",
                    "whatsapp-privacy-policy",
                    False,
                    101,
                    "es",
                ),
                (
                    202,
                    "whatsapp-privacy-policy",
                    "policies",
                    3,
                    "Politique de confidentialite",
                    "Lede FR",
                    "Body FR",
                    "Meta FR",
                    "Description FR",
                    "whatsapp-privacy-policy",
                    False,
                    101,
                    "fr",
                ),
            ]
        ],
        fetchone_results=[
            None,
            (301,),
            None,
            (302,),
        ],
    )

    payload = publish_dcx_admin_content_page_translated_drafts_capability(
        page_key="whatsapp-privacy-policy",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload["page_key"] == "whatsapp-privacy-policy"
    assert payload["published_count"] == 2
    assert payload["published_languages"] == ["es", "fr"]
    assert payload["published_page_ids"] == [301, 302]
    assert payload["previous_page_ids"] == [201, 202]
    assert payload["was_noop"] is False
    assert "FOR UPDATE OF page" in fake_connection.cursor_instance.executed_queries[0][0]


def test_returns_noop_when_page_exists_without_draft_translations() -> None:
    fake_connection = _FakeConnection(
        fetchall_results=[[]],
        fetchone_results=[(1,)],
    )

    payload = publish_dcx_admin_content_page_translated_drafts_capability(
        page_key="whatsapp-privacy-policy",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "page_key": "whatsapp-privacy-policy",
        "published_count": 0,
        "published_languages": [],
        "published_page_ids": [],
        "was_noop": True,
    }
