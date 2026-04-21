from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from admin.content.newsletter_sends.read_dcx_admin_newsletter_sends_catalog import (
    read_dcx_admin_newsletter_sends_catalog_capability,
)


class _FakeCursor:
    def __init__(self, fetchall_results):
        self._fetchall_results = list(fetchall_results)
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


class _FakeConnection:
    def __init__(self, fetchall_results):
        self.cursor_instance = _FakeCursor(fetchall_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


def test_returns_newsletter_send_rows_with_delivery_and_click_summary_counts() -> None:
    fake_connection = _FakeConnection(
        fetchall_results=[
            [
                (
                    901,
                    101,
                    "weekly-alpha",
                    "sent",
                    "newsletters",
                    "all",
                    1777000000000,
                    1777000001000,
                    1777000005000,
                    None,
                    1776999990000,
                    1777000005000,
                    "en",
                    12,
                    10,
                    2,
                    1,
                    0,
                    0,
                    10,
                    8,
                    1,
                    1,
                    0,
                    0,
                    4,
                    7,
                    3,
                ),
                (
                    902,
                    102,
                    "weekly-alpha",
                    "scheduled",
                    "newsletters",
                    "admins",
                    1777100000000,
                    None,
                    None,
                    None,
                    1777099990000,
                    1777099990000,
                    "de",
                    4,
                    3,
                    1,
                    0,
                    3,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    2,
                    0,
                    0,
                ),
            ]
        ]
    )

    payload = read_dcx_admin_newsletter_sends_catalog_capability(
        email_key="weekly-alpha",
        language_code="en",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload["total_send_count"] == 2
    assert payload["newsletter_sends"][0] == {
        "email_send_id": 901,
        "source_email_id": 101,
        "email_key": "weekly-alpha",
        "send_status": "sent",
        "send_audience_type": "newsletters",
        "send_audience_scope": "all",
        "scheduled_send_at_ts_ms": 1777000000000,
        "send_started_at_ts_ms": 1777000001000,
        "send_completed_at_ts_ms": 1777000005000,
        "cancelled_at_ts_ms": None,
        "created_at_ts_ms": 1776999990000,
        "updated_at_ts_ms": 1777000005000,
        "language_code": "en",
        "total_recipient_count": 12,
        "send_candidate_count": 10,
        "skipped_recipient_count": 2,
        "blocked_missing_translation_count": 1,
        "pending_recipient_count": 0,
        "sending_recipient_count": 0,
        "sent_recipient_count": 10,
        "delivered_recipient_count": 8,
        "failed_recipient_count": 1,
        "bounced_recipient_count": 1,
        "complained_recipient_count": 0,
        "cancelled_recipient_count": 0,
        "tracked_link_count": 4,
        "total_click_count": 7,
        "unique_clicked_link_count": 3,
    }
    assert payload["newsletter_sends"][1]["pending_recipient_count"] == 3
    assert payload["newsletter_sends"][1]["tracked_link_count"] == 2
    assert payload["newsletter_sends"][1]["send_audience_scope"] == "admins"
    assert fake_connection.cursor_instance.executed_queries[0][1] == ("weekly-alpha",)
    assert "missing_translation:%%" in fake_connection.cursor_instance.executed_queries[0][0]


def test_returns_empty_catalog_when_no_prepared_sends_exist() -> None:
    fake_connection = _FakeConnection(fetchall_results=[[]])

    payload = read_dcx_admin_newsletter_sends_catalog_capability(
        email_key="weekly-alpha",
        language_code="en",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "newsletter_sends": [],
        "total_send_count": 0,
    }
