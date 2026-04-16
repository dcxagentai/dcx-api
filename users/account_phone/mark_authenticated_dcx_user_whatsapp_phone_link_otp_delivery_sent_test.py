from users.account_phone.mark_authenticated_dcx_user_whatsapp_phone_link_otp_delivery_sent import (
    mark_authenticated_dcx_user_whatsapp_phone_link_otp_delivery_sent,
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


def test_marks_pending_challenge_as_delivered_and_sets_cooldown() -> None:
    mark_authenticated_dcx_user_whatsapp_phone_link_otp_delivery_sent(
        authenticated_user_id=11,
        challenge_id=901,
        connect_to_database=lambda **_: _FakeConnection([(901,)]),
        current_timestamp_ms_provider=lambda: 1776000000000,
    )
