from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from admin.content.newsletters.read_dcx_admin_live_newsletter_detail import (
    read_dcx_admin_live_newsletter_detail_capability,
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


def test_reports_translation_readiness_for_selected_audience_scope() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                101,
                "newsletter",
                "test-newsletter",
                "Test Newsletter",
                "Hello",
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
            ),
        ],
        fetchall_results=[
            [
                (1, "en", "English", "English", False),
                (2, "es", "Spanish", "Espanol", False),
            ],
            [
                (101, "Test Newsletter", True, 1778000000000, 1778001000000, 1, "en", "English", "English", False),
            ],
            [
                (1, "dev@example.com", True, "newsletters", "confirmed", "dev", False),
            ],
        ],
    )

    payload = read_dcx_admin_live_newsletter_detail_capability(
        email_key="test-newsletter",
        language_code="en",
        send_audience_scope="devs",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload["language_readiness"]["send_audience_scope"] == "devs"
    assert payload["language_readiness"]["total_evaluated_recipient_count"] == 1
    assert payload["language_readiness"]["total_send_candidate_count"] == 1
    assert payload["language_readiness"]["total_blocked_missing_translation_count"] == 0
    assert fake_connection.cursor_instance.executed_queries[3][1] == ("devs", "devs", "devs", "devs")


def test_reports_translation_gaps_for_newsletter_eligible_recipients() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                101,
                "newsletter",
                "test-newsletter",
                "Test Newsletter",
                "Hello",
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
            ),
        ],
        fetchall_results=[
            [
                (1, "en", "English", "English", False),
                (2, "es", "Spanish", "Espanol", False),
            ],
            [
                (101, "Test Newsletter", True, 1778000000000, 1778001000000, 1, "en", "English", "English", False),
            ],
            [
                (2, "spanish@example.com", True, "newsletters", "confirmed", "dev", False),
            ],
        ],
    )

    payload = read_dcx_admin_live_newsletter_detail_capability(
        email_key="test-newsletter",
        language_code="en",
        send_audience_scope="devs",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload["language_readiness"]["total_evaluated_recipient_count"] == 1
    assert payload["language_readiness"]["total_send_candidate_count"] == 0
    assert payload["language_readiness"]["total_blocked_missing_translation_count"] == 1
    assert payload["language_readiness"]["missing_languages"][0]["language_code"] == "es"


def test_raises_clear_error_when_live_newsletter_detail_missing() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[None],
        fetchall_results=[
            [],
            [],
            [],
        ],
    )

    try:
        read_dcx_admin_live_newsletter_detail_capability(
            email_key="missing-newsletter",
            language_code="en",
            connect_to_database=lambda **_: fake_connection,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_NEWSLETTER_DETAIL_NOT_FOUND"
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected missing newsletter detail to fail.")
