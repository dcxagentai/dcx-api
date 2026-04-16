"""
CONTEXT:
This file falsifies the persisted public DCX email-signup artifact capability.
It keeps the user/identity/challenge/flow-token contract executable near the capability.
"""

from uuid import UUID

from users.signup_email.create_or_refresh_public_email_signup_artifacts import (
    create_or_refresh_public_email_signup_artifacts_capability,
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


def test_creates_new_user_contact_method_identity_and_pending_challenge_for_new_email(monkeypatch) -> None:
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_OTP_SECRET", "test_secret")
    fake_connection = FakeConnection(
        fetchone_results=[
            None,
            (3,),
            None,
            (101, False, None, "pending_email_verification"),
            (151,),
            (201,),
            None,
            (301,),
        ],
    )
    expected_signup_flow_token = build_public_email_signup_flow_token(
        challenge_id=301,
        flow_token_expires_at_ts_ms=1710001800000,
    )

    payload = create_or_refresh_public_email_signup_artifacts_capability(
        email=" USER@Example.com ",
        language_code="en",
        signup_page_url="http://localhost:4321/?email=leak@example.com",
        origin_header="http://localhost:4321",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1710000000000,
        user_uuid_provider=lambda: UUID("00000000-0000-0000-0000-000000000001"),
        otp_code_provider=lambda: "654321",
        otp_salt_provider=lambda: "saltsaltsaltsalt",
        otp_email_delivery_draft_builder=lambda **kwargs: {
            "recipient_email": kwargs["normalized_email"],
            "subject": "DCX Agentic: Your verification code",
            "text_body": "body",
            "verification_link_url": kwargs["verification_link_url"],
        },
    )

    assert payload["signup_flow_token"] == expected_signup_flow_token
    assert payload["send_required"] is True
    assert payload["challenge_id"] == 301
    assert payload["email_delivery_draft"]["recipient_email"] == "user@example.com"
    assert (
        payload["email_delivery_draft"]["verification_link_url"]
        == f"http://localhost:4321/en/t/verify-otp#signup_flow_token={expected_signup_flow_token}"
    )
    assert payload["delivery_failure_recovery_state"] == {
        "challenge_id": 301,
        "recovery_action": "delete_new_challenge",
    }
    assert any(
        "INSERT INTO stephen_dcx_users_contact_methods" in sql
        for sql, _ in fake_connection.cursor_instance.executed_statements
    )
    assert any(
        "contact_method_id" in sql and "INSERT INTO stephen_dcx_user_auth_identities" in sql
        for sql, _ in fake_connection.cursor_instance.executed_statements
    )


def test_repeated_signup_within_cooldown_reuses_active_challenge_without_fresh_send(monkeypatch) -> None:
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_OTP_SECRET", "test_secret")
    fake_connection = FakeConnection(
        fetchone_results=[
            (1,),
            (3,),
            (151, 101, False, None),
            (101, "pending_email_verification"),
            (201,),
            (
                301,
                "user@example.com",
                "existing_hash",
                "existing_salt",
                1710000600000,
                1709999900000,
                None,
                0,
                5,
                0,
                1,
                1710000050000,
                None,
                "existing_flow_hash",
                1710001200000,
                1709999400000,
                1,
            ),
        ],
    )
    expected_signup_flow_token = build_public_email_signup_flow_token(
        challenge_id=301,
        flow_token_expires_at_ts_ms=1710001200000,
    )

    payload = create_or_refresh_public_email_signup_artifacts_capability(
        email="user@example.com",
        language_code="es",
        signup_page_url="http://localhost:4321/es/?x=1",
        origin_header="http://localhost:4321",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1710000000000,
        user_uuid_provider=lambda: UUID("00000000-0000-0000-0000-000000000001"),
        otp_email_delivery_draft_builder=lambda **kwargs: {
            "recipient_email": kwargs["normalized_email"],
            "subject": "unused",
            "text_body": "unused",
            "verification_link_url": kwargs["verification_link_url"],
        },
    )

    assert payload["send_required"] is False
    assert payload["email_delivery_draft"] is None
    assert payload["challenge_id"] == 301
    assert payload["signup_flow_token"] == expected_signup_flow_token
    assert payload["delivery_failure_recovery_state"]["recovery_action"] == "restore_existing_challenge_state"
    assert any(
        "SELECT" in sql and "FROM stephen_dcx_users_contact_methods" in sql
        for sql, _ in fake_connection.cursor_instance.executed_statements
    )
