"""
CONTEXT:
This file falsifies the public DCX email-signup OTP resend capability.
It keeps the cooldown and flow-token rotation behavior executable near the capability.
"""

from users.signup_email.resend_public_email_signup_otp import (
    resend_public_email_signup_otp_capability,
)
from users.signup_email.public_email_signup_otp_support import (
    build_public_email_signup_flow_token,
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


def test_resend_refreshes_existing_challenge_and_rotates_flow_token(monkeypatch) -> None:
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_OTP_SECRET", "test_secret")
    fake_connection = FakeConnection(
        fetchone_results=[
            (
                301,
                101,
                201,
                "user@example.com",
                "existing_hash",
                "existing_salt",
                1710000600000,
                0,
                1,
                1709999900000,
                None,
                0,
                5,
                1709999990000,
                None,
                "existing_flow_hash",
                1710001200000,
                1709999400000,
                1,
                "pending",
            ),
        ]
    )
    initial_signup_flow_token = build_public_email_signup_flow_token(
        challenge_id=301,
        flow_token_expires_at_ts_ms=1710001200000,
    )
    rotated_signup_flow_token = build_public_email_signup_flow_token(
        challenge_id=301,
        flow_token_expires_at_ts_ms=1710001800000,
    )

    payload = resend_public_email_signup_otp_capability(
        signup_flow_token=initial_signup_flow_token,
        language_code="en",
        resend_page_url="http://localhost:4321/users/signup-email/verify-otp?email=leak@example.com",
        origin_header="http://localhost:4321",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1710000000000,
        otp_code_provider=lambda: "654321",
        otp_salt_provider=lambda: "saltsaltsaltsalt",
    )

    assert payload["status"] == "otp_resent"
    assert payload["signup_flow_token"] == rotated_signup_flow_token
    assert payload["challenge_id"] == 301
    assert payload["email_delivery_draft"]["recipient_email"] == "user@example.com"
    assert (
        payload["email_delivery_draft"]["verification_link_url"]
        == f"http://localhost:4321/users/signup-email/verify-otp#signup_flow_token={rotated_signup_flow_token}"
    )
    assert payload["delivery_failure_recovery_state"] == {
        "challenge_id": 301,
        "recovery_action": "restore_existing_challenge_state",
        "prior_delivery_target": "user@example.com",
        "prior_otp_hash": "existing_hash",
        "prior_otp_salt": "existing_salt",
        "prior_expires_at_ts_ms": 1710000600000,
        "prior_resend_count": 0,
        "prior_send_count": 1,
        "prior_sent_at_ts_ms": 1709999900000,
        "prior_last_attempted_at_ts_ms": None,
        "prior_attempt_count": 0,
        "prior_max_attempt_count": 5,
        "prior_next_send_allowed_at_ts_ms": 1709999990000,
        "prior_locked_until_ts_ms": None,
        "prior_public_signup_flow_token_hash": "existing_flow_hash",
        "prior_public_signup_flow_token_expires_at_ts_ms": 1710001200000,
        "prior_send_budget_window_started_at_ts_ms": 1709999400000,
        "prior_send_budget_request_count": 1,
    }


def test_resend_rejects_cooldown_window(monkeypatch) -> None:
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_OTP_SECRET", "test_secret")
    fake_connection = FakeConnection(
        fetchone_results=[
            (
                301,
                101,
                201,
                "user@example.com",
                "existing_hash",
                "existing_salt",
                1710000600000,
                0,
                1,
                1709999900000,
                None,
                0,
                5,
                1710000050000,
                None,
                "existing_flow_hash",
                1710001200000,
                1709999400000,
                1,
                "pending",
            ),
        ]
    )
    initial_signup_flow_token = build_public_email_signup_flow_token(
        challenge_id=301,
        flow_token_expires_at_ts_ms=1710001200000,
    )

    try:
        resend_public_email_signup_otp_capability(
            signup_flow_token=initial_signup_flow_token,
            language_code="en",
            resend_page_url="http://localhost:4321/users/signup-email/verify-otp",
            origin_header="http://localhost:4321",
            connect_to_database=lambda **_: fake_connection,
            current_timestamp_ms_provider=lambda: 1710000000000,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_PUBLIC_EMAIL_SIGNUP_OTP_RESEND_COOLDOWN_ACTIVE"
    else:
        raise AssertionError("Expected cooldown error.")
