from emails.validate_live_email_template_placeholder_contract import (
    validate_live_email_template_placeholder_contract_capability,
)


def test_allows_valid_signup_verify_otp_placeholders() -> None:
    validate_live_email_template_placeholder_contract_capability(
        email_type="transactional",
        email_key="signup_verify_otp",
        email_subject="DCX Agentic: Your verification code",
        email_body="Code: {{ otp_code }}\nLink: {{ verify_otp_url }}",
    )


def test_rejects_missing_required_placeholder() -> None:
    try:
        validate_live_email_template_placeholder_contract_capability(
            email_type="transactional",
            email_key="signup_verify_otp",
            email_subject="DCX Agentic: Your verification code",
            email_body="Code: {{ otp_code }}",
        )
    except RuntimeError as exc:
        assert str(exc) == "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_REQUIRED_MISSING:verify_otp_url"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected missing required placeholder to raise a stable runtime error.")


def test_rejects_unapproved_placeholder() -> None:
    try:
        validate_live_email_template_placeholder_contract_capability(
            email_type="transactional",
            email_key="signup_verify_otp",
            email_subject="DCX Agentic: Your verification code",
            email_body="Code: {{ otp_code }}\nSupport: {{ support_email }}\nLink: {{ verify_otp_url }}",
        )
    except RuntimeError as exc:
        assert str(exc) == "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_NOT_ALLOWED:support_email"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected unapproved placeholder to raise a stable runtime error.")


def test_rejects_partial_placeholder_syntax() -> None:
    try:
        validate_live_email_template_placeholder_contract_capability(
            email_type="transactional",
            email_key="signup_verify_otp",
            email_subject="DCX Agentic: Your verification code",
            email_body="Code: {{ otp_code }\nLink: {{ verify_otp_url }}",
        )
    except RuntimeError as exc:
        assert str(exc) == "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_SYNTAX_INVALID"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected malformed placeholder syntax to raise a stable runtime error.")
