"""
CONTEXT:
This file owns the admin-facing UX-string translation-create HTTP boundary.
It exists so internal users can create one missing language row from an existing source UX-string route.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from admin.content.ux_strings.create_dcx_admin_ux_string_translation import (
    create_dcx_admin_ux_string_translation_capability,
)
from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_admin_user_id_or_error_response import (
    read_authenticated_dcx_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_ux_string_create_translation_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@dcx_api_routes_admin_content_ux_string_create_translation_router.post(
    "/content/ux-strings/{source_language_code}/{string_group}/{string_key}/translations/{target_language_code}/create",
    response_model=None,
)
def post_dcx_admin_content_ux_string_create_translation(
    request: Request,
    source_language_code: str,
    string_group: str,
    string_key: str,
    target_language_code: str,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX admin/dev session cookie is present.
        - The browser origin is one allowed DCX frontend origin.
        - The path identifies one source UX-string route and one target language.
      postconditions:
        - Creates one first live translation row for the target language and returns the canonical success wrapper.
      side_effects:
        - inserts one new live UX-string translation row
      idempotent: false
      retry_safe: false
      async: false

    NARRATIVE:
      WHY this exists:
        - The admin UX-strings editor needs one direct action to prove the multilingual UX-string model.
      WHEN TO USE it:
        - Use it from the translation summary controls on the admin UX-strings editor.
      WHEN NOT TO USE it:
        - Do not use it to overwrite an existing translation.
      WHAT CAN GO WRONG:
        - The source string may be missing or the target translation may already exist.
      WHAT COMES NEXT:
        - The frontend should navigate to the new UX-string translation route immediately.

    TESTS:
      - covered_indirectly_by_ux_string_translation_create_capability_tests

    ERRORS:
      - API_DCX_ADMIN_UX_STRING_TRANSLATION_ALREADY_EXISTS:
          suggested_action: Open the existing translation instead of creating it again.
          common_causes:
            - the target-language UX-string row already exists
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
        translation_result = create_dcx_admin_ux_string_translation_capability(
            string_group=string_group,
            string_key=string_key,
            source_language_code=source_language_code,
            target_language_code=target_language_code,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        status_code = 400
        if error_code == "API_DCX_ADMIN_UX_STRING_TRANSLATION_SOURCE_NOT_FOUND":
            status_code = 404
        elif error_code == "API_DCX_ADMIN_UX_STRING_TRANSLATION_CREATE_FAILED":
            status_code = 500
        return JSONResponse(
            status_code=status_code,
            content={
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": "We could not create that DCX UX-string translation.",
                    "suggested_action": "Refresh the current UX-string route and retry from the translation controls.",
                },
            },
        )

    return {
        "ok": True,
        "data": translation_result,
        "context": {
            "surface": "admin",
            "view": "ux_strings_catalog",
            "operation": "translation_created",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
