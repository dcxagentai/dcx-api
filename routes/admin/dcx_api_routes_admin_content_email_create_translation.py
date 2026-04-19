"""
CONTEXT:
This file owns the admin-facing transactional-email translation-create HTTP boundary.
It exists so internal users can create one missing language row from an existing source transactional email route.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.emails.create_dcx_admin_email_translation import (
    create_dcx_admin_email_translation_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_email_create_translation_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_email_create_translation_router.post(
    "/content/emails/{source_language_code}/{email_key}/translations/{target_language_code}/create",
    response_model=None,
)
def post_dcx_admin_content_email_create_translation(
    request: Request,
    source_language_code: str,
    email_key: str,
    target_language_code: str,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The browser origin is one allowed DCX frontend origin.
        - The path identifies one source transactional-email route and one target language.
      postconditions:
        - Creates one first live translation row for the target language and returns the canonical success wrapper.
      side_effects:
        - inserts one new live transactional-email translation row
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin transactional-email editor needs one direct action to prove the multilingual transactional-template model.
      WHEN TO USE it:
        - Use it from the translation summary controls on the admin transactional-email editor.
      WHEN NOT TO USE it:
        - Do not use it to overwrite an existing translation.
        - Do not use it for newsletters.
      WHAT CAN GO WRONG:
        - The source email may be missing or the target translation may already exist.
      WHAT COMES NEXT:
        - The frontend should navigate to the new transactional-email translation route immediately.

    TESTS:
      - covered_indirectly_by_email_translation_create_capability_tests

    ERRORS:
      - API_DCX_ADMIN_EMAIL_TRANSLATION_ALREADY_EXISTS:
          suggested_action: Open the existing translation instead of creating it again.
          common_causes:
            - the target-language email row already exists
          recovery_steps:
            - Open the current translation from the translation list.
          retry_safe: true

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    _, identity_resolution_mode, error_response = read_authenticated_dcx_admin_user_id_or_error_response(
        request=request,
    )
    if error_response is not None:
        return error_response

    try:
        translation_result = create_dcx_admin_email_translation_capability(
            email_key=email_key,
            source_language_code=source_language_code,
            target_language_code=target_language_code,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = 400
        if error_code == "API_DCX_ADMIN_EMAIL_TRANSLATION_SOURCE_NOT_FOUND":
            status_code = 404
        elif error_code == "API_DCX_ADMIN_EMAIL_TRANSLATION_CREATE_FAILED":
            status_code = 500
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not create that DCX transactional email translation.",
                    "suggested_action": "Refresh the current transactional email route and retry from the translation controls.",
                },
            },
        )

    return {
        "ok": True,
        "data": translation_result,
        "context": {
            "surface": "admin",
            "view": "emails_catalog",
            "operation": "translation_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
