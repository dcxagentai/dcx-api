from auth.password.dcx_password_link_challenge_support import (
    DCX_PASSWORD_RESET_CHALLENGE_PURPOSE,
    DCX_PASSWORD_SETUP_CHALLENGE_PURPOSE,
    build_dcx_password_link_challenge_token,
    build_dcx_password_set_page_url,
    hash_dcx_password_link_challenge_token,
    normalize_dcx_password_link_challenge_token,
)


def test_token_roundtrip_hash_normalize_path() -> None:
    raw_token = build_dcx_password_link_challenge_token()
    normalized_token = normalize_dcx_password_link_challenge_token(raw_token)
    hashed_token = hash_dcx_password_link_challenge_token(normalized_token)

    assert normalized_token == raw_token
    assert len(hashed_token) == 64


def test_normalize_rejects_short_token() -> None:
    try:
        normalize_dcx_password_link_challenge_token("too-short")
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_PASSWORD_LINK_TOKEN_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Short token should be rejected.")


def test_builds_setup_and_reset_urls_against_local_default(monkeypatch) -> None:
    monkeypatch.delenv("DCX_APP_BASE_URL", raising=False)
    monkeypatch.setenv("DCX_ENVIRONMENT", "local")

    assert build_dcx_password_set_page_url(
        DCX_PASSWORD_SETUP_CHALLENGE_PURPOSE,
        "setup-token",
    ) == "http://localhost:5173/password/set?mode=password_setup#password_challenge_token=setup-token"
    assert build_dcx_password_set_page_url(
        DCX_PASSWORD_RESET_CHALLENGE_PURPOSE,
        "reset-token",
    ) == "http://localhost:5173/password/set?mode=password_reset#password_challenge_token=reset-token"
