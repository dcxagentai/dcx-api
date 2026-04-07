from unittest.mock import patch

from auth.session.read_dcx_auth_session_cookie_settings import (
    read_dcx_auth_session_cookie_settings,
)


def test_cookie_settings_default_for_local_runtime() -> None:
    with patch.dict("os.environ", {"DCX_ENVIRONMENT": "local"}, clear=False):
        result = read_dcx_auth_session_cookie_settings()

    assert result["cookie_name"] == "dcx_session"
    assert result["cookie_domain"] is None
    assert result["cookie_secure"] is False
    assert result["cookie_same_site"] == "lax"
