"""
CONTEXT:
This file reads the first app-account-page UX-string group for the DCX user app.
It exists so the `/me/account` surface can move onto the shared `stephen_dcx_ux_strings`
model without waiting for every translation row to exist on day one.
"""

from __future__ import annotations

from typing import Any, Callable

from languages.read_live_dcx_ux_string_group_with_language_fallback import (
    read_live_dcx_ux_string_group_with_language_fallback_capability,
)

DCX_APP_ACCOUNT_PAGE_UX_STRING_GROUP = "app_account_page"

DCX_APP_ACCOUNT_PAGE_DEFAULT_UX_STRINGS = {
    "surface_label": "DCX App",
    "page_title": "Account",
    "inline_autosave_badge": "Inline autosave MVP surface",
    "local_debug_user_label_prefix": "Local debug user:",
    "refresh_button_label": "Refresh",
    "loading_account_summary": "Loading account summary...",
    "error_account_read_blocked": "Account read blocked",
    "error_account_load_title": "We could not load the DCX account summary.",
    "identity_eyebrow": "Identity",
    "identity_subtitle": "Confirmed account with stable DCX user identity.",
    "account_state_confirmed": "Confirmed",
    "account_state_pending": "Pending",
    "field_primary_email": "Primary email",
    "field_primary_phone": "Primary phone",
    "field_user_uuid": "User UUID",
    "field_account_status": "Account status",
    "field_preferred_language": "Preferred language",
    "field_timezone": "Timezone",
    "field_email_preference": "Email preference",
    "field_email_confirmed_at": "Email confirmed at",
    "field_phone_confirmed_at": "Phone confirmed at",
    "field_last_seen_at": "Last seen at",
    "field_created_at": "Created at",
    "field_updated_at": "Updated at",
    "field_not_set": "Not set",
    "field_phone_not_set_yet": "Not set yet",
    "logout_button_pending_label": "Signing out...",
    "logout_button_label": "Logout",
    "editable_status_idle": "Blue means editable. Click to adjust.",
    "editable_status_editing": "Editing. Choose a value to autosave.",
    "editable_status_saving": "Saving...",
    "editable_status_saved": "Saved.",
    "editable_status_retrying_template": "Retrying save ({attempt}/{total})...",
    "editable_status_save_failed": "Save failed. Please click back in and retry.",
    "editable_status_saving_default_language": "Saving default language...",
    "error_account_load_suggested_action": "Sign in again through the DCX app login flow, then retry.",
    "activity_eyebrow": "Activity",
    "activity_title": "Account timeline",
    "email_preference_announcements": "Announcements",
    "email_preference_essential_only": "Essential only",
    "next_eyebrow": "Next",
    "next_title": "Email and phone changes can come after the field behavior is proven.",
    "next_body": "This pass intentionally keeps primary email and phone read-only. Preferred language, timezone, and communication preference now prove the inline autosave behavior, retry path, and save-state feedback we can reuse later for higher-risk account changes.",
}


def read_dcx_app_account_page_ux_strings_capability(
    preferred_language_code: str | None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict[str, str]:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable when DB-backed UX strings should be loaded.
        - preferred_language_code is either null or one language code from `stephen_dcx_languages`.
      postconditions:
        - Returns one complete app-account-page UX-string map.
        - Falls back to the local English defaults when DB rows are missing or not yet seeded.
        - Prefers the selected language row, then the original live row, then the local default.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The first app surface should move onto the shared multilingual UX-string model now,
          while still staying resilient during the early English-only seeding phase.
      WHEN TO USE it:
        - Use it while assembling the `/me/account` account-summary payload.
      WHEN NOT TO USE it:
        - Do not use it for the public Astro site bundle or admin UX-string catalog.
      WHAT CAN GO WRONG:
        - The DB can be unreachable.
        - The app-account-page group may not be seeded yet.
        - Selected-language rows may be incomplete while translations are still in progress.
      WHAT COMES NEXT:
        - Once the group is seeded in English and then translated, this read path will naturally
          start serving translated account copy without another frontend refactor.

    TESTS:
      - returns_defaults_when_group_has_not_been_seeded
      - overlays_selected_language_rows_on_top_of_original_rows

    ERRORS:
      - API_DCX_APP_ACCOUNT_PAGE_UX_STRINGS_READ_FAILED:
          suggested_action: Confirm database health and retry after the backend is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend and database are healthy.
          retry_safe: true

    CODE:
    """
    try:
        return read_live_dcx_ux_string_group_with_language_fallback_capability(
            string_group=DCX_APP_ACCOUNT_PAGE_UX_STRING_GROUP,
            language_code=preferred_language_code or "en",
            default_ux_strings=DCX_APP_ACCOUNT_PAGE_DEFAULT_UX_STRINGS,
            connect_to_database=connect_to_database,
        )
    except RuntimeError as exc:
        if str(exc) == "API_LIVE_DCX_UX_STRING_GROUP_READ_FAILED":
            raise RuntimeError("API_DCX_APP_ACCOUNT_PAGE_UX_STRINGS_READ_FAILED") from exc
        raise
