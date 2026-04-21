from emails.apply_dcx_resend_email_event_to_send_records import (
    apply_dcx_resend_email_event_to_send_records_capability,
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


def test_applies_delivered_event_to_matching_recipient() -> None:
    fake_connection = _FakeConnection(fetchone_results=[(701, 7, 501, "alpha@example.com")])

    payload = apply_dcx_resend_email_event_to_send_records_capability(
        webhook_payload={
            "type": "email.delivered",
            "created_at": "2026-04-20T12:00:00Z",
            "data": {"email_id": "msg_123"},
        },
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000000,
    )

    assert payload["status"] == "applied"
    assert payload["event_type"] == "email.delivered"


def test_applies_bounced_event_and_creates_all_email_suppression() -> None:
    fake_connection = _FakeConnection(fetchone_results=[(701, 7, 501, "alpha@example.com"), None])

    payload = apply_dcx_resend_email_event_to_send_records_capability(
        webhook_payload={
            "type": "email.bounced",
            "created_at": "2026-04-20T12:00:00Z",
            "data": {
                "email_id": "msg_123",
                "bounce": {"message": "Mailbox unavailable"},
            },
        },
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000000,
    )

    assert payload["status"] == "applied"
    assert any("INSERT INTO stephen_dcx_emails_suppressions" in query for query, _ in fake_connection.cursor_instance.executed_queries)


def test_ignores_unmatched_provider_message_id() -> None:
    fake_connection = _FakeConnection(fetchone_results=[None])

    payload = apply_dcx_resend_email_event_to_send_records_capability(
        webhook_payload={
            "type": "email.delivered",
            "created_at": "2026-04-20T12:00:00Z",
            "data": {"email_id": "msg_missing"},
        },
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "status": "ignored",
        "event_type": "email.delivered",
        "provider_message_id": "msg_missing",
        "reason": "recipient_not_found",
    }
