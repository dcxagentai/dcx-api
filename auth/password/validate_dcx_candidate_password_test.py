from auth.password.validate_dcx_candidate_password import validate_dcx_candidate_password


def test_accepts_password_with_length_twelve_or_more() -> None:
    payload = validate_dcx_candidate_password(
        candidate_password="correct horse battery",
        confirmed_password="correct horse battery",
    )

    assert payload["normalized_candidate_password"] == "correct horse battery"


def test_rejects_blank_candidate_password() -> None:
    try:
        validate_dcx_candidate_password(candidate_password="   ")
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_PASSWORD_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Blank password should be rejected.")


def test_rejects_short_candidate_password() -> None:
    try:
        validate_dcx_candidate_password(candidate_password="too-short")
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_PASSWORD_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Short password should be rejected.")


def test_rejects_confirmation_mismatch() -> None:
    try:
        validate_dcx_candidate_password(
            candidate_password="correct horse battery",
            confirmed_password="correct horse battery!",
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_DCX_PASSWORD_CONFIRMATION_MISMATCH"
    else:  # pragma: no cover - defensive
        raise AssertionError("Password confirmation mismatch should be rejected.")
