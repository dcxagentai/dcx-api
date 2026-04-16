from users.account_phone.read_authenticated_dcx_user_pending_whatsapp_phone_link import (
    read_authenticated_dcx_user_pending_whatsapp_phone_link,
)


class _FakeCursor:
    def __init__(self, fetchone_results):
        self._fetchone_results = list(fetchone_results)

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchone(self):
        if not self._fetchone_results:
            return None
        return self._fetchone_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, fetchone_results):
        self._fetchone_results = fetchone_results

    def cursor(self):
        return _FakeCursor(self._fetchone_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_returns_pending_whatsapp_phone_link_when_delivered_challenge_exists() -> None:
    result = read_authenticated_dcx_user_pending_whatsapp_phone_link(
        authenticated_user_id=7,
        connect_to_database=lambda **_: _FakeConnection(
            [
                (
                    "+34600000001",
                    "pending",
                    1776000000000,
                    1775999400000,
                    1775999460000,
                    None,
                    1,
                    2,
                    1775999400000,
                )
            ]
        ),
        current_timestamp_ms_provider=lambda: 1775999410000,
    )

    assert result == {
        "phone_e164": "+34600000001",
        "challenge_status": "pending",
        "expires_at_ts_ms": 1776000000000,
        "sent_at_ts_ms": 1775999400000,
        "next_send_allowed_at_ts_ms": 1775999460000,
        "locked_until_ts_ms": None,
        "resend_count": 1,
        "send_count": 2,
        "last_resent_at_ts_ms": 1775999400000,
    }


def test_returns_null_when_only_undelivered_pending_challenge_exists() -> None:
    result = read_authenticated_dcx_user_pending_whatsapp_phone_link(
        authenticated_user_id=7,
        connect_to_database=lambda **_: _FakeConnection([None]),
        current_timestamp_ms_provider=lambda: 1775999410000,
    )

    assert result is None
