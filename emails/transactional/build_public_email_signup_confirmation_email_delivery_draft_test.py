"""
CONTEXT:
This file falsifies the managed-template confirmation email draft builder.
It keeps the DB-backed confirmation subject/body rendering executable near the transactional builder.
"""

from emails.transactional.build_public_email_signup_confirmation_email_delivery_draft import (
    build_public_email_signup_confirmation_email_delivery_draft,
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


def test_builds_confirmation_delivery_draft_from_live_template() -> None:
    fake_connection = FakeConnection(
        fetchone_results=[
            (
                2,
                "fr",
                "DCX Agentic : Votre inscription est confirmée",
                "Merci.\nDCX Agentic",
                False,
            ),
        ]
    )

    payload = build_public_email_signup_confirmation_email_delivery_draft(
        language_code="fr",
        normalized_email="user@example.com",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "recipient_email": "user@example.com",
        "subject": "DCX Agentic : Votre inscription est confirmée",
        "text_body": "Merci.\nDCX Agentic",
    }
