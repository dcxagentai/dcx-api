from users.account.apply_dcx_public_email_unsubscribe_request import (
    apply_dcx_public_email_unsubscribe_request_capability,
)
from users.account.dcx_email_preference_unsubscribe_support import (
    build_dcx_email_preference_unsubscribe_token,
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


def test_unsubscribe_all_sets_user_preference_to_no_email(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    raw_token = build_dcx_email_preference_unsubscribe_token(
        user_id=7,
        recipient_email="alpha@example.com",
        unsubscribe_kind="all",
        current_timestamp_ms_provider=lambda: 1778000000000,
    )
    fake_connection = _FakeConnection(
        fetchone_results=[
            (7, "all_email", 19, "alpha@example.com"),
            ("no_email",),
        ]
    )

    payload = apply_dcx_public_email_unsubscribe_request_capability(
        unsubscribe_kind="all",
        raw_unsubscribe_token=raw_token,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000001,
    )

    assert payload["email_communication_preference"] == "no_email"
    assert payload["newsletters_suppressed"] is False


def test_unsubscribe_promotional_steps_down_to_newsletters(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    raw_token = build_dcx_email_preference_unsubscribe_token(
        user_id=7,
        recipient_email="alpha@example.com",
        unsubscribe_kind="promotional",
        current_timestamp_ms_provider=lambda: 1778000000000,
    )
    fake_connection = _FakeConnection(
        fetchone_results=[
            (7, "all_email", 19, "alpha@example.com"),
            ("newsletters",),
        ]
    )

    payload = apply_dcx_public_email_unsubscribe_request_capability(
        unsubscribe_kind="promotional",
        raw_unsubscribe_token=raw_token,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000001,
    )

    assert payload["email_communication_preference"] == "newsletters"
    assert payload["newsletters_suppressed"] is False


def test_unsubscribe_newsletters_from_all_email_creates_newsletter_suppression(monkeypatch) -> None:
    monkeypatch.setenv("DCX_AUTH_CHALLENGE_SECRET", "test_secret")
    raw_token = build_dcx_email_preference_unsubscribe_token(
        user_id=7,
        recipient_email="alpha@example.com",
        unsubscribe_kind="newsletters",
        current_timestamp_ms_provider=lambda: 1778000000000,
    )
    fake_connection = _FakeConnection(
        fetchone_results=[
            (7, "all_email", 19, "alpha@example.com"),
            None,
            ("all_email",),
        ]
    )

    payload = apply_dcx_public_email_unsubscribe_request_capability(
        unsubscribe_kind="newsletters",
        raw_unsubscribe_token=raw_token,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1778000000001,
    )

    assert payload["email_communication_preference"] == "all_email"
    assert payload["newsletters_suppressed"] is True
