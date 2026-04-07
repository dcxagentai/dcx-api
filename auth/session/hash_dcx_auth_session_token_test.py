from auth.session.hash_dcx_auth_session_token import hash_dcx_auth_session_token


def test_hashes_session_token_deterministically() -> None:
    assert hash_dcx_auth_session_token("abc") == hash_dcx_auth_session_token("abc")
    assert hash_dcx_auth_session_token("abc") != hash_dcx_auth_session_token("xyz")
