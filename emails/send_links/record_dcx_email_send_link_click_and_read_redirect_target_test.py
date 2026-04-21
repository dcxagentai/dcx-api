from emails.send_links.record_dcx_email_send_link_click_and_read_redirect_target import (
    record_dcx_email_send_link_click_and_read_redirect_target_capability,
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


def test_records_click_and_returns_redirect_target_for_valid_tracking_token() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[
            (31, 501, "https://dcxagent.ai/market"),
            (9001,),
        ]
    )

    payload = record_dcx_email_send_link_click_and_read_redirect_target_capability(
        tracking_token="track-123",
        request_ip="203.0.113.10",
        request_user_agent="DCX Test Browser",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000000,
    )

    assert payload == {
        "click_id": 9001,
        "email_send_id": 501,
        "email_send_link_id": 31,
        "original_url": "https://dcxagent.ai/market",
        "tracking_token": "track-123",
        "clicked_at_ts_ms": 1778000000000,
    }
    assert fake_connection.cursor_instance.executed_queries[1][1] == (
        501,
        31,
        1778000000000,
        "203.0.113.10",
        "DCX Test Browser",
    )


def test_raises_clear_error_when_tracking_token_missing() -> None:
    try:
        record_dcx_email_send_link_click_and_read_redirect_target_capability(
            tracking_token="   ",
            request_ip=None,
            request_user_agent=None,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_EMAIL_SEND_LINK_REDIRECT_INVALID"
    else:  # pragma: no cover - test guard
        raise AssertionError("Expected invalid tracking-token error")


def test_raises_clear_error_when_tracking_token_not_found() -> None:
    fake_connection = _FakeConnection(fetchone_results=[None])

    try:
        record_dcx_email_send_link_click_and_read_redirect_target_capability(
            tracking_token="missing-token",
            request_ip=None,
            request_user_agent=None,
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1778000000000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_EMAIL_SEND_LINK_REDIRECT_NOT_FOUND"
    else:  # pragma: no cover - test guard
        raise AssertionError("Expected not-found tracking-token error")
