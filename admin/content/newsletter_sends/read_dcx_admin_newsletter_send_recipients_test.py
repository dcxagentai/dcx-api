from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from admin.content.newsletter_sends.read_dcx_admin_newsletter_send_recipients import (
    read_dcx_admin_newsletter_send_recipients_capability,
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


def test_returns_summary_counts_and_first_twenty_five_recipient_rows() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (3, 0, 0, 0, 3, 0, 0, 0, 0, 0),
            (3,),
        ],
        fetchall_results=[
            [
                (
                    1,
                    11,
                    "first@example.com",
                    "dev",
                    "send",
                    "delivered",
                    "msg_1",
                    1778087437423,
                    1778087439467,
                    None,
                    None,
                    None,
                    None,
                    1778087439467,
                    "email.delivered",
                    "en",
                    "English",
                    "English",
                ),
            ],
        ],
    )

    payload = read_dcx_admin_newsletter_send_recipients_capability(
        email_send_id=1,
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload["summary"]["total_recipient_count"] == 3
    assert payload["summary"]["delivered_recipient_count"] == 3
    assert payload["filtered_recipient_count"] == 3
    assert payload["visible_rows_limit"] == 25
    assert payload["recipients"][0]["recipient_email"] == "first@example.com"
    assert payload["recipients"][0]["preferred_language"]["language_code"] == "en"


def test_filters_visible_recipient_rows_by_email_without_changing_summary_totals() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (3, 0, 0, 0, 3, 0, 0, 0, 0, 0),
            (1,),
        ],
        fetchall_results=[
            [
                (
                    2,
                    12,
                    "jill.whitney@ncmedia.ch",
                    "shareholder",
                    "send",
                    "delivered",
                    "msg_2",
                    1778087437423,
                    1778087440667,
                    None,
                    None,
                    None,
                    None,
                    1778087440667,
                    "email.delivered",
                    "en",
                    "English",
                    "English",
                ),
            ],
        ],
    )

    payload = read_dcx_admin_newsletter_send_recipients_capability(
        email_send_id=1,
        email_search="JILL",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload["email_search"] == "jill"
    assert payload["summary"]["total_recipient_count"] == 3
    assert payload["filtered_recipient_count"] == 1
    assert payload["recipients"][0]["user_role"] == "shareholder"
    assert fake_connection.cursor_instance.executed_queries[1][1] == (1, "jill", "jill")


def test_returns_empty_result_for_invalid_send_id() -> None:
    payload = read_dcx_admin_newsletter_send_recipients_capability(email_send_id=0)

    assert payload["email_send_id"] == 0
    assert payload["summary"]["total_recipient_count"] == 0
    assert payload["recipients"] == []
