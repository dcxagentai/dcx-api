from users.account_phone.dcx_whatsapp_phone_link_otp_support import (
    hash_dcx_whatsapp_phone_link_otp_code,
)
from users.account_phone.verify_authenticated_dcx_user_whatsapp_phone_link_otp import (
    verify_authenticated_dcx_user_whatsapp_phone_link_otp,
)


class _FakeCursor:
    def __init__(self, fetchone_results):
        self._fetchone_results = list(fetchone_results)
        self.executed_statements = []

    def execute(self, sql, params=None):
        self.executed_statements.append((sql, params))

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
        self.cursor_instance = _FakeCursor(fetchone_results)

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_correct_otp_links_phone_and_consumes_pending_challenge(monkeypatch) -> None:
    monkeypatch.setenv("DCX_WHATSAPP_PHONE_OTP_SECRET", "test_secret")
    otp_hash = hash_dcx_whatsapp_phone_link_otp_code("123456", "saltsaltsaltsalt")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                901,
                "+34600000001",
                otp_hash,
                "saltsaltsaltsalt",
                1776000600000,
                1776000000000,
                0,
                5,
                None,
                "pending",
            ),
            None,
            None,
            None,
            (301,),
            None,
            (401,),
        ]
    )

    result = verify_authenticated_dcx_user_whatsapp_phone_link_otp(
        authenticated_user_id=44,
        candidate_otp_code="123456",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1776000010000,
    )

    assert result == {
        "status": "verified",
        "phone_e164": "+34600000001",
        "whatsapp_identity_id": 401,
    }


def test_incorrect_otp_increments_attempt_count(monkeypatch) -> None:
    monkeypatch.setenv("DCX_WHATSAPP_PHONE_OTP_SECRET", "test_secret")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                901,
                "+34600000001",
                "different_hash",
                "saltsaltsaltsalt",
                1776000600000,
                1776000000000,
                1,
                5,
                None,
                "pending",
            ),
        ]
    )

    try:
        verify_authenticated_dcx_user_whatsapp_phone_link_otp(
            authenticated_user_id=44,
            candidate_otp_code="123456",
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1776000010000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_LINK_OTP_VERIFICATION_FAILED"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected incorrect OTP to raise a stable runtime error.")


def test_duplicate_phone_conflict_after_send_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("DCX_WHATSAPP_PHONE_OTP_SECRET", "test_secret")
    otp_hash = hash_dcx_whatsapp_phone_link_otp_code("123456", "saltsaltsaltsalt")
    fake_connection = _FakeConnection(
        fetchone_results=[
            (
                901,
                "+34600000001",
                otp_hash,
                "saltsaltsaltsalt",
                1776000600000,
                1776000000000,
                0,
                5,
                None,
                "pending",
            ),
            (91,),
        ]
    )

    try:
        verify_authenticated_dcx_user_whatsapp_phone_link_otp(
            authenticated_user_id=44,
            candidate_otp_code="123456",
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1776000010000,
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_ALREADY_LINKED_TO_ANOTHER_USER"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected phone conflict to raise a stable runtime error.")
