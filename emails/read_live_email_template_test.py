"""
CONTEXT:
This file falsifies the live DCX email-template reader.
It keeps the database-backed email lookup and fallback behavior executable near the capability.
"""

from emails.read_live_email_template import read_live_email_template_capability


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


def test_returns_requested_live_translation_when_language_exists() -> None:
    fake_connection = FakeConnection(
        fetchone_results=[
            (12, "es", "Asunto", "Cuerpo", False),
        ]
    )

    payload = read_live_email_template_capability(
        email_type="transactional",
        email_key="signup_verify_otp",
        language_code="es",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "template_id": 12,
        "language_code": "es",
        "email_subject": "Asunto",
        "email_body": "Cuerpo",
        "is_original": False,
    }


def test_falls_back_to_live_original_when_translation_missing() -> None:
    fake_connection = FakeConnection(
        fetchone_results=[
            (1, "en", "Original subject", "Original body", True),
        ]
    )

    payload = read_live_email_template_capability(
        email_type="transactional",
        email_key="signup_verify_otp",
        language_code="fr",
        connect_to_database=lambda **_: fake_connection,
    )

    assert payload == {
        "template_id": 1,
        "language_code": "en",
        "email_subject": "Original subject",
        "email_body": "Original body",
        "is_original": True,
    }


def test_raises_clear_error_when_no_live_template_exists() -> None:
    fake_connection = FakeConnection(fetchone_results=[None])

    try:
        read_live_email_template_capability(
            email_type="transactional",
            email_key="signup_verify_otp",
            language_code="en",
            connect_to_database=lambda **_: fake_connection,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_LIVE_EMAIL_TEMPLATE_NOT_FOUND"
    else:
        raise AssertionError("Expected live email template not found error.")
