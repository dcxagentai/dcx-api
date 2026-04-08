"""
CONTEXT:
This file reads one live DCX UX-string group with requested-language fallback behavior.
It exists so app, auth, and future internal surfaces can all resolve localized UX copy from
`stephen_dcx_ux_strings` without duplicating the same selected-language/original/default merge logic.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_live_dcx_ux_string_group_with_language_fallback_capability(
    string_group: str,
    language_code: str,
    default_ux_strings: dict[str, str],
    connect_to_database: Callable[..., Any] | None = None,
) -> dict[str, str]:
    """
    CONTRACT:
      preconditions:
        - string_group identifies one live UX-string group in `stephen_dcx_ux_strings`.
        - language_code is the requested best language code for this browser or user context.
        - default_ux_strings contains the complete local fallback map for the group.
      postconditions:
        - Returns one complete UX-string map for the requested group.
        - Prefers the requested live translation row when it exists.
        - Falls back to the live original row when the requested translation is missing.
        - Falls back to the provided local default when the DB does not yet contain the key.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Multiple DCX surfaces now need the same multilingual UX resolution contract, and keeping
          that behavior in one capability avoids drift between auth, app, and future surfaces.
      WHEN TO USE it:
        - Use it when a backend capability needs one localized UX-string group.
      WHEN NOT TO USE it:
        - Do not use it for email templates because the email system has its own subject/body contract.
      WHAT CAN GO WRONG:
        - The database can be unavailable.
        - The group may not be seeded yet.
        - Requested-language rows may be incomplete while translations are still being added.
      WHAT COMES NEXT:
        - Higher-level capabilities can project this resolved map into app or auth responses without
          carrying query logic of their own.

    TESTS:
      - returns_defaults_when_group_has_not_been_seeded
      - overlays_requested_language_rows_on_top_of_original_rows
      - ignores_unknown_string_keys_not_present_in_defaults

    ERRORS:
      - API_LIVE_DCX_UX_STRING_GROUP_READ_FAILED:
          suggested_action: Confirm database health and retry once the backend is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true

    CODE:
    """
    normalized_language_code = (
        language_code.strip().lower()
        if isinstance(language_code, str) and language_code.strip() != ""
        else "en"
    )
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        u.string_key,
                        u.text,
                        u.is_original,
                        l.language_code
                    FROM stephen_dcx_ux_strings u
                    JOIN stephen_dcx_languages l
                      ON l.id = u.language_id
                    WHERE u.is_live = TRUE
                      AND u.string_group = %s
                      AND (
                        l.language_code = %s
                        OR u.is_original = TRUE
                      )
                    ORDER BY
                        u.string_key ASC,
                        CASE WHEN l.language_code = %s THEN 0 ELSE 1 END,
                        CASE WHEN u.is_original = TRUE THEN 0 ELSE 1 END,
                        u.id ASC
                    """,
                    (
                        string_group,
                        normalized_language_code,
                        normalized_language_code,
                    ),
                )
                live_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_LIVE_DCX_UX_STRING_GROUP_READ_FAILED") from exc

    resolved_strings = dict(default_ux_strings)

    for string_key, text, is_original, row_language_code in live_rows:
        if string_key not in resolved_strings:
            continue

        if row_language_code == normalized_language_code:
            resolved_strings[string_key] = text
            continue

        if is_original and resolved_strings[string_key] == default_ux_strings[string_key]:
            resolved_strings[string_key] = text

    return resolved_strings
