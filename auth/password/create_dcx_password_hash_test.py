from auth.password.create_dcx_password_hash import create_dcx_password_hash
from auth.password.verify_dcx_password_hash import verify_dcx_password_hash


def test_password_hash_roundtrip_verifies_successfully() -> None:
    password_hash = create_dcx_password_hash("correct horse battery staple")

    assert password_hash.startswith("$argon2id$")
    assert verify_dcx_password_hash("correct horse battery staple", password_hash) is True


def test_verify_returns_false_for_wrong_password() -> None:
    password_hash = create_dcx_password_hash("correct horse battery staple")

    assert verify_dcx_password_hash("wrong password", password_hash) is False
