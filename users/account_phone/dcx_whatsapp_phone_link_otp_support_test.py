from users.account_phone.dcx_whatsapp_phone_link_otp_support import (
    generate_dcx_whatsapp_phone_link_otp_code,
    hash_dcx_whatsapp_phone_link_otp_code,
    normalize_dcx_whatsapp_phone_link_otp_code,
    normalize_dcx_whatsapp_phone_link_phone_e164,
)


def test_normalizes_phone_with_spaces_hyphens_and_00_prefix() -> None:
    assert normalize_dcx_whatsapp_phone_link_phone_e164("00 34 600-000-001") == "+34600000001"


def test_raises_clear_error_for_invalid_phone_shape() -> None:
    try:
        normalize_dcx_whatsapp_phone_link_phone_e164("600000001")
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid phone shape to raise a stable runtime error.")


def test_normalizes_six_digit_otp() -> None:
    assert normalize_dcx_whatsapp_phone_link_otp_code(" 123456 ") == "123456"


def test_raises_clear_error_for_invalid_otp_shape() -> None:
    try:
        normalize_dcx_whatsapp_phone_link_otp_code("12ab56")
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_WHATSAPP_PHONE_OTP_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid OTP shape to raise a stable runtime error.")


def test_hashes_same_otp_and_salt_deterministically(monkeypatch) -> None:
    monkeypatch.setenv("DCX_WHATSAPP_PHONE_OTP_SECRET", "test_secret")

    first_hash = hash_dcx_whatsapp_phone_link_otp_code("123456", "saltsalt")
    second_hash = hash_dcx_whatsapp_phone_link_otp_code("123456", "saltsalt")

    assert first_hash == second_hash


def test_falls_back_to_email_signup_secret_when_whatsapp_secret_missing(monkeypatch) -> None:
    monkeypatch.delenv("DCX_WHATSAPP_PHONE_OTP_SECRET", raising=False)
    monkeypatch.setenv("DCX_EMAIL_SIGNUP_OTP_SECRET", "email_secret")

    result = hash_dcx_whatsapp_phone_link_otp_code("123456", "saltsalt")

    assert isinstance(result, str)
    assert len(result) == 64


def test_generate_otp_code_returns_six_digits() -> None:
    result = generate_dcx_whatsapp_phone_link_otp_code()

    assert len(result) == 6
    assert result.isdigit()
