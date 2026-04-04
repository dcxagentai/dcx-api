"""
CONTEXT:
This file reads the live DCX public UX strings from Postgres and assembles one language-first
bundle for the Astro public site.
It exists so the public frontend can treat the database as the source of truth for public copy
while still building static language routes from one generated bundle.
"""

from __future__ import annotations

from typing import Final

import psycopg2

from storage.db_config import DB_CONFIG

DCX_PUBLIC_SUPPORTED_LANGUAGE_CODES: Final[tuple[str, ...]] = ("en", "es", "fr", "de")
DCX_PUBLIC_SUPPORTED_UX_STRING_GROUPS: Final[tuple[str, ...]] = (
    "home",
    "signup_form",
    "signup_otp_page",
    "signup_otp_form",
    "signup_confirmation_page",
)


def read_live_dcx_public_ux_strings_bundle() -> dict[str, dict[str, dict[str, str]]]:
    """
    CONTRACT:
      preconditions:
        - DB_CONFIG resolves one working Postgres connection for the configured DCX database.
        - stephen_dcx_ux_strings contains one live row per string_group, string_key, and language for the public site.
      postconditions:
        - Returns one nested bundle keyed by language_code, then string_group, then string_key.
        - Includes only the supported public languages and supported public UX-string groups.
        - Excludes non-live rows.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why:
        - The Astro public site should not hardcode route copy once the UX-string table exists.
        - We still want static builds, so we need one clean read path that turns the live DB rows into a frontend bundle.
      when_to_use:
        - Use this immediately before exporting the generated public UX-string file.
        - Use it whenever we need the live language copy for the current public routes.
      when_not_to_use:
        - Do not use it for transactional email templates or future admin-edit workflows.
        - Do not use it for non-public language content that belongs to another frontend.
      what_can_go_wrong:
        - The database can be unreachable.
        - One language or group can be missing rows.
        - A duplicate live row would indicate broken data integrity outside this reader.
      what_comes_next:
        - The export step can serialize this bundle into a generated TypeScript file for Astro.

    TESTS:
      - builds_language_first_bundle_from_live_rows
      - ignores_non_live_rows_and_unknown_groups

    ERRORS:
      - API_PUBLIC_UX_STRINGS_DB_UNAVAILABLE:
          suggested_action: Confirm the configured DCX database is reachable and try the export again.
          common_causes:
            - local database credentials missing
            - database temporarily unavailable
            - wrong database selected
          recovery_steps:
            - Check DB_CONFIG and connectivity.
            - Retry once the database is reachable.
          retry_safe: true
      - API_PUBLIC_UX_STRINGS_LANGUAGE_UNKNOWN:
          suggested_action: Seed the missing language in stephen_dcx_languages or stop exporting that language.
          common_causes:
            - unsupported language row in stephen_dcx_ux_strings
            - typo in language_code data
          recovery_steps:
            - Fix the row language reference and re-run the export.
          retry_safe: true

    CODE:
    """
    bundle: dict[str, dict[str, dict[str, str]]] = {
        language_code: {
            string_group: {}
            for string_group in DCX_PUBLIC_SUPPORTED_UX_STRING_GROUPS
        }
        for language_code in DCX_PUBLIC_SUPPORTED_LANGUAGE_CODES
    }

    try:
        with psycopg2.connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        dcx_languages.language_code,
                        dcx_ux_strings.string_group,
                        dcx_ux_strings.string_key,
                        dcx_ux_strings.text
                    FROM stephen_dcx_ux_strings AS dcx_ux_strings
                    JOIN stephen_dcx_languages AS dcx_languages
                      ON dcx_languages.id = dcx_ux_strings.language_id
                    WHERE dcx_ux_strings.is_live = TRUE
                      AND dcx_languages.language_code = ANY(%s)
                      AND dcx_ux_strings.string_group = ANY(%s)
                    ORDER BY
                        dcx_languages.language_code,
                        dcx_ux_strings.string_group,
                        dcx_ux_strings.string_key
                    """,
                    (
                        list(DCX_PUBLIC_SUPPORTED_LANGUAGE_CODES),
                        list(DCX_PUBLIC_SUPPORTED_UX_STRING_GROUPS),
                    ),
                )
                live_rows = cursor.fetchall()
    except Exception as exc:  # pragma: no cover - exercised through monkeypatched failure path
        raise RuntimeError("API_PUBLIC_UX_STRINGS_DB_UNAVAILABLE") from exc

    for language_code, string_group, string_key, text in live_rows:
        if language_code not in bundle:
            raise RuntimeError("API_PUBLIC_UX_STRINGS_LANGUAGE_UNKNOWN")

        bundle[language_code][string_group][string_key] = text

    return bundle
