from admin.content.newsletter_sends.prepare_dcx_admin_newsletter_send import (
    prepare_dcx_admin_newsletter_send_capability,
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


def test_creates_send_row_recipient_snapshots_and_link_rows() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (101, "weekly-alpha", 1, "Weekly Alpha", "[CTA](https://dcxagent.ai/en/access)", "en"),
            (501,),
            (601,),
        ],
        fetchall_results=[
            [
                (101, 1, "Weekly Alpha", "[CTA](https://dcxagent.ai/en/access)", "en"),
            ],
            [
                (11, "eligible@example.com", True, 1, "announcements", "confirmed"),
                (12, "skip@example.com", True, 1, "essential_only", "confirmed"),
            ],
        ],
    )

    payload = prepare_dcx_admin_newsletter_send_capability(
        authenticated_admin_user_id=7,
        email_key="weekly-alpha",
        language_code="en",
        scheduled_send_at_ts_ms=None,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1776000000000,
        tracking_token_provider=lambda: "track-token-1",
    )

    assert payload["email_send_id"] == 501
    assert payload["send_status"] == "scheduled"
    assert payload["summary"] == {
        "prepared_recipient_count": 2,
        "send_candidate_count": 1,
        "skipped_recipient_count": 1,
        "tracked_link_count": 1,
    }


def test_falls_back_to_source_newsletter_when_no_language_match_exists() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (101, "weekly-alpha", 1, "Weekly Alpha", "https://dcxagent.ai/en/access", "en"),
            (502,),
            (602,),
        ],
        fetchall_results=[
            [
                (101, 1, "Weekly Alpha", "https://dcxagent.ai/en/access", "en"),
            ],
            [
                (11, "eligible@example.com", True, 3, "announcements", "confirmed"),
            ],
        ],
    )

    payload = prepare_dcx_admin_newsletter_send_capability(
        authenticated_admin_user_id=7,
        email_key="weekly-alpha",
        language_code="en",
        scheduled_send_at_ts_ms=1777000000000,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1776000000000,
        tracking_token_provider=lambda: "track-token-2",
    )

    assert payload["summary"]["send_candidate_count"] == 1
    assert payload["summary"]["tracked_link_count"] == 1


def test_raises_clear_error_when_source_newsletter_missing() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[None],
        fetchall_results=[],
    )

    try:
        prepare_dcx_admin_newsletter_send_capability(
            authenticated_admin_user_id=7,
            email_key="missing-newsletter",
            language_code="en",
            scheduled_send_at_ts_ms=None,
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1776000000000,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_NEWSLETTER_SEND_SOURCE_NOT_FOUND"
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected source newsletter lookup to fail.")
