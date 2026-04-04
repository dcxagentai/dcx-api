"""
CONTEXT:
This file falsifies the managed-template OTP email draft builder.
It keeps the DB-backed OTP subject/body rendering executable near the transactional builder.
"""

from emails.transactional.build_public_email_signup_otp_email_delivery_draft import (
    build_public_email_signup_otp_email_delivery_draft,
)


class FakeCursor:
    def __init__(self, fetchone_results):
        self.fetchone_results = list(fetchone_results)

    def execute(self, sql, params=None):
        return None

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


def test_builds_otp_delivery_draft_from_live_template_with_rendered_placeholders() -> None:
    fake_connection = FakeConnection(
        fetchone_results=[
            (
                1,
                "en",
                "DCX Agentic: Your verification code",
                "Code:\n\n{{ otp_code }}\n\nLink:\n{{ verify_otp_url }}",
                True,
            ),
        ]
    )

    payload = build_public_email_signup_otp_email_delivery_draft(
        language_code="en",
        normalized_email="user@example.com",
        otp_code="123456",
        verification_link_url="https://dcxagent.ai/en/t/verify-otp#signup_flow_token=abc",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "provider": "resend",
        "recipient_email": "user@example.com",
        "subject": "DCX Agentic: Your verification code",
        "text_body": (
            "Code:\n\n123456\n\nLink:\n"
            "https://dcxagent.ai/en/t/verify-otp#signup_flow_token=abc"
        ),
        "verification_link_url": "https://dcxagent.ai/en/t/verify-otp#signup_flow_token=abc",
    }
