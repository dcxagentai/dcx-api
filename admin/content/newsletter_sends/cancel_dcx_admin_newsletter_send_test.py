from admin.content.newsletter_sends.cancel_dcx_admin_newsletter_send import (
    cancel_dcx_admin_newsletter_send_capability,
)


class _FakeCursor:
    def __init__(self, fetchone_results):
        self._fetchone_results = list(fetchone_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params

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


def test_cancels_one_scheduled_newsletter_send() -> None:
    fake_connection = _FakeConnection([(501, "cancelled", 1777000000000)])

    payload = cancel_dcx_admin_newsletter_send_capability(
        authenticated_admin_user_id=7,
        email_send_id=501,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1777000000000,
    )

    assert payload == {
        "email_send_id": 501,
        "send_status": "cancelled",
        "cancelled_at_ts_ms": 1777000000000,
    }


def test_raises_clear_error_when_send_missing_or_not_cancellable() -> None:
    fake_connection = _FakeConnection([None])

    try:
        cancel_dcx_admin_newsletter_send_capability(
            authenticated_admin_user_id=7,
            email_send_id=501,
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1777000000000,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_ADMIN_NEWSLETTER_SEND_CANCEL_NOT_ALLOWED"
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected cancel capability to reject the missing/non-scheduled row.")
