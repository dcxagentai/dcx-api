from admin.content.newsletters.create_dcx_admin_newsletter_translation import (
    create_dcx_admin_newsletter_translation_capability,
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


def test_creates_translation_row_from_source_newsletter() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (101, "weekly-alpha", "Weekly Alpha", "Hello body"),
            (3,),
            None,
            (101,),
            (501,),
        ]
    )

    payload = create_dcx_admin_newsletter_translation_capability(
        email_key="weekly-alpha",
        source_language_code="en",
        target_language_code="fr",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "email_id": 501,
        "email_key": "weekly-alpha",
        "language_code": "fr",
    }


def test_raises_clear_error_when_newsletter_translation_already_exists() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (101, "weekly-alpha", "Weekly Alpha", "Hello body"),
            (3,),
            (301,),
        ]
    )

    try:
        create_dcx_admin_newsletter_translation_capability(
            email_key="weekly-alpha",
            source_language_code="en",
            target_language_code="fr",
            connect_to_database=lambda **_: fake_connection,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_NEWSLETTER_TRANSLATION_ALREADY_EXISTS"
    else:  # pragma: no cover
        raise AssertionError("Expected translation create to fail when the target row already exists.")
