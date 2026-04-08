from auth.password.create_or_refresh_dcx_password_link_challenge import (
    create_or_refresh_dcx_password_link_challenge,
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
        self._cursor = _FakeCursor(fetchone_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


def test_creates_new_pending_password_link_challenge_when_none_exists() -> None:
    fake_connection = _FakeConnection([None, (301,)])

    payload = create_or_refresh_dcx_password_link_challenge(
        authenticated_user_id=11,
        authenticated_user_identity_id=21,
        challenge_purpose="password_setup",
        delivery_target_email="setup@example.com",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1775000000000,
        raw_token_provider=lambda: "raw-setup-password-token-value",
    )

    assert payload["challenge_id"] == 301
    assert payload["challenge_purpose"] == "password_setup"
    assert payload["password_set_url"].endswith(
        "/password/set?mode=password_setup&language_code=en#password_challenge_token=raw-setup-password-token-value"
    )


def test_refreshes_existing_pending_password_link_challenge() -> None:
    fake_connection = _FakeConnection([(401,)])

    payload = create_or_refresh_dcx_password_link_challenge(
        authenticated_user_id=12,
        authenticated_user_identity_id=22,
        challenge_purpose="password_reset",
        delivery_target_email="reset@example.com",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1775000000000,
        raw_token_provider=lambda: "raw-reset-password-token-value",
    )

    assert payload["challenge_id"] == 401
    assert payload["challenge_purpose"] == "password_reset"


def test_builds_password_link_url_with_requested_language_code() -> None:
    fake_connection = _FakeConnection([None, (901,)])

    payload = create_or_refresh_dcx_password_link_challenge(
        authenticated_user_id=13,
        authenticated_user_identity_id=23,
        challenge_purpose="password_reset",
        delivery_target_email="reset@example.com",
        language_code="fr",
        connect_to_database=lambda **_: fake_connection,
        current_timestamp_ms_provider=lambda: 1775000000000,
        raw_token_provider=lambda: "raw-reset-password-token-value",
    )

    assert payload["password_set_url"].endswith(
        "/password/set?mode=password_reset&language_code=fr#password_challenge_token=raw-reset-password-token-value"
    )
