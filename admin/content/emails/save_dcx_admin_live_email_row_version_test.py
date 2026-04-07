from admin.content.emails.save_dcx_admin_live_email_row_version import (
    save_dcx_admin_live_email_row_version_capability,
)


class _FakeCursor:
    def __init__(self, fetchone_results):
        self._fetchone_results = list(fetchone_results)
        self.executed_queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed_queries.append((query, params))

    def fetchone(self):
        if not self._fetchone_results:
            return None
        return self._fetchone_results.pop(0)


class _FakeConnection:
    def __init__(self, fetchone_results):
        self._fetchone_results = fetchone_results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._fetchone_results)


def test_inserts_new_live_version_when_subject_or_body_changes() -> None:
    result = save_dcx_admin_live_email_row_version_capability(
        target_email_id=11,
        next_email_subject="DCX Agentic: Ihr Bestätigungscode",
        next_email_body="Code: {{ otp_code }}\nLink: {{ verify_otp_url }}",
        connect_to_database=lambda **_: _FakeConnection(
            [
                (
                    11,
                    "transactional",
                    "signup_verify_otp",
                    4,
                    "Old subject",
                    "Old body {{ otp_code }}\n{{ verify_otp_url }}",
                    False,
                    1,
                ),
                (22,),
            ]
        ),
    )

    assert result == {
        "email_id": 22,
        "previous_email_id": 11,
        "was_noop": False,
    }


def test_returns_noop_when_subject_and_body_are_unchanged() -> None:
    result = save_dcx_admin_live_email_row_version_capability(
        target_email_id=11,
        next_email_subject="Same subject",
        next_email_body="Same body",
        connect_to_database=lambda **_: _FakeConnection(
            [
                (
                    11,
                    "transactional",
                    "signup_thanks_welcome",
                    4,
                    "Same subject",
                    "Same body",
                    False,
                    2,
                ),
            ]
        ),
    )

    assert result == {
        "email_id": 11,
        "was_noop": True,
    }


def test_raises_clear_error_for_blank_subject_or_body() -> None:
    try:
        save_dcx_admin_live_email_row_version_capability(
            target_email_id=11,
            next_email_subject=" ",
            next_email_body="Valid body",
            connect_to_database=lambda **_: _FakeConnection([]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_ADMIN_EMAIL_TEMPLATE_CONTENT_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected blank email content to raise a stable runtime error.")


def test_raises_clear_error_for_missing_live_row() -> None:
    try:
        save_dcx_admin_live_email_row_version_capability(
            target_email_id=11,
            next_email_subject="Valid subject",
            next_email_body="Valid body",
            connect_to_database=lambda **_: _FakeConnection([None]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_ADMIN_EMAIL_LIVE_ROW_NOT_FOUND"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected missing live email row to raise a stable runtime error.")


def test_raises_clear_error_for_invalid_placeholder_contract() -> None:
    try:
        save_dcx_admin_live_email_row_version_capability(
            target_email_id=11,
            next_email_subject="DCX Agentic: Ihr Bestätigungscode",
            next_email_body="Code: {{ otp_code }}",
            connect_to_database=lambda **_: _FakeConnection(
                [
                    (
                        11,
                        "transactional",
                        "signup_verify_otp",
                        4,
                        "Old subject",
                        "Old body {{ otp_code }}\n{{ verify_otp_url }}",
                        False,
                        1,
                    ),
                ]
            ),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_DCX_ADMIN_EMAIL_TEMPLATE_PLACEHOLDER_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid placeholder contract to raise a stable runtime error.")
