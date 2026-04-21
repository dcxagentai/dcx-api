from content.newsletter_sends.dispatch_one_due_dcx_newsletter_send_via_resend import (
    dispatch_one_due_dcx_newsletter_send_via_resend_capability,
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


def test_returns_idle_when_no_due_newsletter_send_exists() -> None:
    fake_connection = _FakeConnection(
        fetchone_results=[None],
        fetchall_results=[],
    )

    payload = dispatch_one_due_dcx_newsletter_send_via_resend_capability(
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000000,
    )

    assert payload == {
        "status": "idle",
        "dispatched_send": None,
    }


def test_dispatches_due_newsletter_send_and_updates_recipient_rows(monkeypatch) -> None:
    monkeypatch.setenv("DCX_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (501, "weekly-alpha"),
            (2, 2, 0, 0, 0),
        ],
        fetchall_results=[
            [
                ("https://dcxagent.ai/market", "track-1"),
            ],
            [
                (701, 31, "alpha@example.com", 101, "Weekly Alpha", "Read [Market](https://dcxagent.ai/market)"),
                (702, 32, "beta@example.com", 101, "Weekly Alpha", "Visit https://dcxagent.ai/market"),
            ],
        ],
    )
    sent_drafts = []

    payload = dispatch_one_due_dcx_newsletter_send_via_resend_capability(
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000000,
        send_email=lambda draft: sent_drafts.append(draft) or {"provider_message_id": f"msg-{len(sent_drafts)}"},
    )

    assert payload["status"] == "dispatched"
    assert payload["dispatched_send"]["email_send_id"] == 501
    assert payload["dispatched_send"]["send_status"] == "sent"
    assert payload["dispatched_send"]["summary"]["sent_recipient_count"] == 2
    assert payload["dispatched_send"]["failed_recipient_reasons"] == []
    assert len(sent_drafts) == 2
    assert sent_drafts[0]["subject"] == "Weekly Alpha"
    assert "Market: https://api.example.com/public/email-links/track-1" in sent_drafts[0]["text_body"]
    assert "Unsubscribe from promotional email: https://api.example.com/public/email-preferences/unsubscribe/promotional/" in sent_drafts[0]["text_body"]
    assert "<a href=\"https://api.example.com/public/email-links/track-1\"" in sent_drafts[0]["html_body"]


def test_marks_parent_send_failed_when_any_recipient_send_fails() -> None:
    import os

    os.environ["DCX_AUTH_CHALLENGE_SECRET"] = "test_secret"
    fake_connection = _FakeConnection(
        fetchone_results=[
            (502, "weekly-beta"),
            (2, 1, 1, 0, 0),
        ],
        fetchall_results=[
            [],
            [
                (703, 31, "alpha@example.com", 102, "Weekly Beta", "Hello world"),
                (704, 32, "beta@example.com", 102, "Weekly Beta", "Hello world"),
            ],
        ],
    )

    send_attempt_count = {"value": 0}

    def fake_send_email(draft: dict) -> dict:
        send_attempt_count["value"] += 1
        if send_attempt_count["value"] == 2:
            raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED") from ValueError(
                "resend rejected sender"
            )
        return {"provider_message_id": "msg-1"}

    payload = dispatch_one_due_dcx_newsletter_send_via_resend_capability(
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000000,
        send_email=fake_send_email,
    )

    assert payload["dispatched_send"]["email_send_id"] == 502
    assert payload["dispatched_send"]["send_status"] == "failed"
    assert payload["dispatched_send"]["summary"]["failed_recipient_count"] == 1
    assert payload["dispatched_send"]["failed_recipient_reasons"] == [
        {
            "recipient_id": 704,
            "recipient_email": "beta@example.com",
            "failure_reason": "API_PUBLIC_EMAIL_SIGNUP_RESEND_SEND_FAILED [ValueError: resend rejected sender]",
        }
    ]
