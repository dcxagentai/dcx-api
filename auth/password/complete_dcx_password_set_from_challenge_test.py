from unittest.mock import patch

import auth.password.complete_dcx_password_set_from_challenge as complete_password_module


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


def test_complete_password_set_creates_password_credential_and_consumes_challenge() -> None:
    with patch.object(
        complete_password_module,
        "create_dcx_password_hash",
        return_value="$argon2id$hashed",
    ), patch.object(
        complete_password_module,
        "revoke_all_dcx_auth_sessions_for_user",
        return_value={"revoked_count": 1},
    ) as revoke_mock:
        payload = complete_password_module.complete_dcx_password_set_from_challenge(
            raw_password_link_token="complete-token-value-1234567890",
            candidate_password="correct horse battery",
            confirmed_password="correct horse battery",
            connect_to_database=lambda **_: _FakeConnection(
                [
                    (
                        701,
                        81,
                        "password_setup",
                        1775003600000,
                    )
                ]
            ),
            current_timestamp_ms_provider=lambda: 1775000000000,
        )

    assert payload["user_id"] == 81
    revoke_mock.assert_called_once()


def test_complete_password_set_rejects_expired_challenge() -> None:
    try:
        complete_password_module.complete_dcx_password_set_from_challenge(
            raw_password_link_token="expired-token-value-1234567890",
            candidate_password="correct horse battery",
            confirmed_password="correct horse battery",
            connect_to_database=lambda **_: _FakeConnection(
                [
                    (
                        702,
                        82,
                        "password_reset",
                        1774000000000,
                    )
                ]
            ),
            current_timestamp_ms_provider=lambda: 1775000000000,
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_PASSWORD_CHALLENGE_EXPIRED"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expired password challenge should be rejected.")
