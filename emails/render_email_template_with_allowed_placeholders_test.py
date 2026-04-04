"""
CONTEXT:
This file falsifies the strict DCX email-template placeholder renderer.
It keeps placeholder safety and substitution behavior executable near the renderer capability.
"""

from emails.render_email_template_with_allowed_placeholders import (
    render_email_template_with_allowed_placeholders_capability,
)


def test_renders_repeated_allowed_placeholders_in_subject_and_body() -> None:
    payload = render_email_template_with_allowed_placeholders_capability(
        email_subject="Code {{ otp_code }}",
        email_body="Use {{ otp_code }} at {{ verify_otp_url }}",
        allowed_placeholder_codes={"otp_code", "verify_otp_url"},
        placeholder_values={
            "otp_code": "123456",
            "verify_otp_url": "https://dcxagent.ai/en/t/verify-otp#signup_flow_token=abc",
        },
    )

    assert payload == {
        "email_subject": "Code 123456",
        "email_body": "Use 123456 at https://dcxagent.ai/en/t/verify-otp#signup_flow_token=abc",
    }


def test_rejects_unapproved_placeholder_codes() -> None:
    try:
        render_email_template_with_allowed_placeholders_capability(
            email_subject="Hello",
            email_body="Unsupported {{ support_email }}",
            allowed_placeholder_codes={"otp_code"},
            placeholder_values={"otp_code": "123456"},
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_NOT_ALLOWED:support_email"
    else:
        raise AssertionError("Expected unsupported placeholder error.")


def test_rejects_missing_placeholder_values() -> None:
    try:
        render_email_template_with_allowed_placeholders_capability(
            email_subject="Code {{ otp_code }}",
            email_body="Body",
            allowed_placeholder_codes={"otp_code"},
            placeholder_values={},
        )
    except RuntimeError as runtime_error:
        assert str(runtime_error) == "API_LIVE_EMAIL_TEMPLATE_PLACEHOLDER_VALUE_MISSING:otp_code"
    else:
        raise AssertionError("Expected missing placeholder value error.")
