"""
CONTEXT:
This file falsifies the DCX public email-signup delivery-failure recovery capability.
It keeps the state-restore mutation executable near the capability.
"""

from users.signup_email.reset_public_email_signup_send_cooldown_after_delivery_failure import (
    reset_public_email_signup_send_cooldown_after_delivery_failure_capability,
)


class FakeCursor:
    def __init__(self):
        self.executed_statements = []

    def execute(self, sql, params=None):
        self.executed_statements.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_restores_prior_send_counters_and_cooldown_for_failed_delivery() -> None:
    fake_connection = FakeConnection()

    payload = reset_public_email_signup_send_cooldown_after_delivery_failure_capability(
        challenge_id=301,
        recovery_action="restore_existing_challenge_state",
        prior_delivery_target="user@example.com",
        prior_otp_hash="existing_hash",
        prior_otp_salt="existing_salt",
        prior_expires_at_ts_ms=1710000300000,
        prior_sent_at_ts_ms=1710000000000,
        prior_last_attempted_at_ts_ms=None,
        prior_attempt_count=0,
        prior_max_attempt_count=5,
        prior_resend_count=0,
        prior_send_count=1,
        prior_next_send_allowed_at_ts_ms=1710000060000,
        prior_locked_until_ts_ms=None,
        prior_public_signup_flow_token_hash="existing_flow_hash",
        prior_public_signup_flow_token_expires_at_ts_ms=1710001800000,
        prior_send_budget_window_started_at_ts_ms=1709999400000,
        prior_send_budget_request_count=1,
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1710000005000,
    )

    assert payload == {
        "challenge_id": 301,
        "recovery_action": "restore_existing_challenge_state",
    }
    assert "FOR UPDATE" in fake_connection.cursor_instance.executed_statements[0][0]
    assert "send_count = %s" in fake_connection.cursor_instance.executed_statements[1][0]
    assert "public_signup_flow_token_hash = %s" in fake_connection.cursor_instance.executed_statements[1][0]


def test_deletes_new_unsent_challenge_after_failed_delivery() -> None:
    fake_connection = FakeConnection()

    payload = reset_public_email_signup_send_cooldown_after_delivery_failure_capability(
        challenge_id=302,
        recovery_action="delete_new_challenge",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1710000005000,
    )

    assert payload == {
        "challenge_id": 302,
        "recovery_action": "delete_new_challenge",
    }
    assert "DELETE FROM stephen_dcx_user_auth_challenges" in fake_connection.cursor_instance.executed_statements[1][0]
