from unittest.mock import patch

from auth.logout.logout_authenticated_dcx_user import logout_authenticated_dcx_user


def test_logout_returns_logged_out_true_even_without_session_token() -> None:
    result = logout_authenticated_dcx_user(None)

    assert result == {
        "logged_out": True,
        "session_revoked": False,
    }


def test_logout_revokes_current_session_when_token_present() -> None:
    with patch(
        "auth.logout.logout_authenticated_dcx_user.revoke_dcx_auth_session_by_token",
        return_value={"session_revoked": True},
    ):
        result = logout_authenticated_dcx_user("raw-token")

    assert result == {
        "logged_out": True,
        "session_revoked": True,
    }
