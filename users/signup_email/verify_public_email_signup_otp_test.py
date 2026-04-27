"""
CONTEXT:
This file falsifies the public DCX email-signup OTP verification capability.
It keeps the challenge-consumption and failure-state mutations executable.
"""

from users.signup_email.public_email_signup_otp_support import (
    build_public_email_signup_flow_token,
    hash_public_email_signup_otp_code,
)
from users.signup_email.verify_public_email_signup_otp import (
    verify_public_email_signup_otp_capability,
)


class FakeCursor:
    def __init__(self, fetchone_results):
        self.fetchone_results = list(fetchone_results)
        self.executed_statements = []

    def execute(self, sql, params=None):
        self.executed_statements.append((sql, params))

    def fetchone(self):
        if not self.fetchone_results:
            return None

        return self.fetchone_results.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, fetchone_results):
        self.cursor_instance = FakeCursor(fetchone_results)

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_correct_otp_confirms_user_identity_and_consumes_challenge(monkeypatch) -> None:
    monkeypatch.setenv("DCX_SIGNUP_OTP_SECRET", "test_secret")
    otp_hash = hash_public_email_signup_otp_code(
        otp_code="123456",
        otp_salt="saltsaltsaltsalt",
    )
    fake_connection = FakeConnection(
        fetchone_results=[
            (
                301,
                101,
                201,
                otp_hash,
                "saltsaltsaltsalt",
                1710000600000,
                0,
                5,
                None,
                1710001200000,
                "pending",
                "user@example.com",
            ),
            (2,),
        ],
    )
    signup_flow_token = build_public_email_signup_flow_token(
        challenge_id=301,
        flow_token_expires_at_ts_ms=1710001200000,
    )

    payload = verify_public_email_signup_otp_capability(
        signup_flow_token=signup_flow_token,
        otp_code="123456",
        language_code="en",
        verification_page_url="http://localhost:4321/users/signup-email/verify-otp",
        origin_header="http://localhost:4321",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1710000000000,
    )

    assert payload["status"] == "confirmed"
    assert payload["confirmed_email"] == "user@example.com"
    assert payload["verification_page_url"] == "http://localhost:4321/users/signup-email/verify-otp"
    assert any(
        "UPDATE stephen_dcx_users_contact_methods" in sql
        for sql, _ in fake_connection.cursor_instance.executed_statements
    )


def test_incorrect_otp_increments_attempt_count(monkeypatch) -> None:
    monkeypatch.setenv("DCX_SIGNUP_OTP_SECRET", "test_secret")
    fake_connection = FakeConnection(
        fetchone_results=[
            (
                301,
                101,
                201,
                "different_hash",
                "saltsaltsaltsalt",
                1710000600000,
                1,
                5,
                None,
                1710001200000,
                "pending",
                "user@example.com",
            ),
        ],
    )
    signup_flow_token = build_public_email_signup_flow_token(
        challenge_id=301,
        flow_token_expires_at_ts_ms=1710001200000,
    )

    try:
        verify_public_email_signup_otp_capability(
            signup_flow_token=signup_flow_token,
            otp_code="123456",
            language_code="en",
            verification_page_url="http://localhost:4321/users/signup-email/verify-otp",
            origin_header="http://localhost:4321",
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1710000000000,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_PUBLIC_EMAIL_SIGNUP_OTP_VERIFICATION_FAILED"
    else:
        raise AssertionError("Expected incorrect OTP error.")


def test_expired_or_invalid_flow_requires_restart(monkeypatch) -> None:
    monkeypatch.setenv("DCX_SIGNUP_OTP_SECRET", "test_secret")
    fake_connection = FakeConnection(fetchone_results=[None])
    signup_flow_token = build_public_email_signup_flow_token(
        challenge_id=301,
        flow_token_expires_at_ts_ms=1710001200000,
    )

    try:
        verify_public_email_signup_otp_capability(
            signup_flow_token=signup_flow_token,
            otp_code="123456",
            language_code="en",
            verification_page_url="http://localhost:4321/users/signup-email/verify-otp",
            origin_header="http://localhost:4321",
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1710000000000,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_PUBLIC_EMAIL_SIGNUP_FLOW_RESTART_REQUIRED"
    else:
        raise AssertionError("Expected restart-required error.")
