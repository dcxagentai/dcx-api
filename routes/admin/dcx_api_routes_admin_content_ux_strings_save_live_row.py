"""
CONTEXT:
This file owns the first admin-facing UX-string save HTTP boundary.
It exists so the admin frontend can autosave one selected live UX-string row into a new
immutable version while the broader admin auth system is still being built.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from admin.content.ux_strings.save_dcx_admin_live_ux_string_row_version import (
    save_dcx_admin_live_ux_string_row_version_capability,
)
from routes.admin.dcx_api_routes_admin_support import (
    read_permitted_local_debug_admin_user_id_or_error_response,
)

dcx_api_routes_admin_content_ux_strings_save_live_row_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


class DcxAdminContentUxStringsSaveLiveRowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ux_string_id: int
    text: str


@dcx_api_routes_admin_content_ux_strings_save_live_row_router.post(
    "/content/ux-strings/save-live-row",
    response_model=None,
)
def post_dcx_admin_content_ux_strings_save_live_row(
    ux_strings_save_live_row_request: DcxAdminContentUxStringsSaveLiveRowRequest,
    admin_user_id: int | None = Query(default=None, ge=1),
):
    """
    CONTRACT:
      preconditions:
        - Real admin auth is not wired yet, so local development may temporarily supply one
          `admin_user_id` query parameter for screen testing.
        - The body contains one current live UX-string row id and one candidate replacement text value.
      postconditions:
        - Saves one new immutable live row version or returns a no-op when the text is unchanged.
        - Returns a canonical success wrapper with the save result metadata.
      side_effects:
        - updates one current live UX-string row to `is_live = false`
        - inserts one new live UX-string row when the text changed
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first admin UX-string editor needs one precise autosave endpoint without exposing direct table writes.
      WHEN TO USE it:
        - Use it from the selected-language UX-string panel only.
      WHEN NOT TO USE it:
        - Do not use it to create new string identities or delete content.
      WHAT CAN GO WRONG:
        - No temporary local admin identity is present yet.
        - The target row can be stale.
        - The edited text can be blank.
        - Database writes can fail.
      WHAT COMES NEXT:
        - Keep this save route stable while admin auth and permission checks replace the local debug path.

    TESTS:
      - test_admin_ux_strings_save_live_row_route_returns_save_result_for_local_debug_admin_user_id
      - test_admin_ux_strings_save_live_row_route_returns_auth_required_without_debug_identity

    ERRORS:
      - API_DCX_ADMIN_AUTH_REQUIRED:
          suggested_action: Use `?admin_user_id=` locally until admin auth is connected.
          common_causes:
            - no authenticated admin session yet
          recovery_steps:
            - Add `?admin_user_id=<existing_user_id>` during local development.
          retry_safe: true
      - API_DCX_ADMIN_UX_STRING_SAVE_INVALID:
          suggested_action: Refresh the selected row and retry with non-empty text.
          common_causes:
            - blank text
            - stale live row id
          recovery_steps:
            - Refresh the catalog.
            - Retry from the current live row with valid text.
          retry_safe: true

    CODE:
    """
    _, error_response = read_permitted_local_debug_admin_user_id_or_error_response(admin_user_id)
    if error_response is not None:
        return error_response

    try:
        save_result = save_dcx_admin_live_ux_string_row_version_capability(
            target_ux_string_id=ux_strings_save_live_row_request.ux_string_id,
            next_text=ux_strings_save_live_row_request.text,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)

        if error_code in {
            "API_DCX_ADMIN_UX_STRING_TEXT_INVALID",
            "API_DCX_ADMIN_UX_STRING_LIVE_ROW_NOT_FOUND",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_DCX_ADMIN_UX_STRING_SAVE_INVALID",
                        "message": "We could not save that UX-string row.",
                        "suggested_action": "Refresh the row and retry with non-empty text.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_ADMIN_UX_STRING_SAVE_FAILED",
                    "message": "We could not save the DCX UX-string row just now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": save_result,
        "context": {
            "surface": "admin",
            "view": "ux_strings_catalog",
            "operation": "live_row_saved",
            "identity_resolution_mode": "temporary_admin_user_id_query_parameter",
        },
    }
