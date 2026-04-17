"""
CONTEXT:
This file reads the active DCX countries reference bundle.
It exists so app, admin, and later trade flows can reuse one database-backed source of truth
for country display metadata and phone-calling-code options instead of scattering hardcoded
country lists across multiple frontends.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_active_dcx_reference_countries_bundle(
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The configured database is reachable.
      postconditions:
        - Returns every active country row with its active calling-code rows nested underneath.
        - Orders countries predictably by sort_order and display name.
        - Orders each country's calling-code rows with primary-first precedence.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The DCX product is already treating phone and geography as global concerns, and those concerns
          need one reusable backend reference contract before trade geography expands.
        - The account phone picker is the first real consumer of this shared countries model.
      WHEN TO USE it:
        - Use it from frontend surfaces that need the active supported countries bundle.
        - Use it when building country-aware pickers, labels, or later trade-region flows.
      WHEN NOT TO USE it:
        - Do not use it to infer phone ownership or verification state.
        - Do not use it as a substitute for E.164 normalization.
      WHAT CAN GO WRONG:
        - Database reads can fail.
        - Seed data can be incomplete or inconsistent.
      WHAT COMES NEXT:
        - Later flows can layer translations, trade regions, and country-specific compliance metadata
          on top of this same core reference bundle.

    TESTS:
      - returns_active_countries_with_nested_calling_codes
      - returns_empty_bundle_when_no_active_countries_exist

    ERRORS:
      - API_DCX_REFERENCE_COUNTRIES_READ_FAILED:
          suggested_action: Confirm database health and retry the countries read after the backend is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true

    CODE:
    """
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        country.id,
                        country.country_code_alpha2,
                        country.default_display_name,
                        country.flag_asset_key,
                        country.sort_order,
                        calling_code.id,
                        calling_code.calling_code,
                        calling_code.is_primary,
                        calling_code.sort_order
                    FROM stephen_dcx_countries AS country
                    LEFT JOIN stephen_dcx_country_calling_codes AS calling_code
                      ON calling_code.country_id = country.id
                     AND calling_code.is_active = TRUE
                    WHERE country.is_active = TRUE
                    ORDER BY
                        country.sort_order ASC,
                        country.default_display_name ASC,
                        country.id ASC,
                        calling_code.is_primary DESC NULLS LAST,
                        calling_code.sort_order ASC NULLS LAST,
                        calling_code.calling_code ASC NULLS LAST,
                        calling_code.id ASC NULLS LAST
                    """
                )
                country_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_REFERENCE_COUNTRIES_READ_FAILED") from exc

    countries_by_id: dict[int, dict] = {}
    ordered_country_ids: list[int] = []

    for country_row in country_rows:
        country_id = country_row[0]
        if country_id not in countries_by_id:
            countries_by_id[country_id] = {
                "id": country_id,
                "country_code_alpha2": country_row[1],
                "default_display_name": country_row[2],
                "flag_asset_key": country_row[3],
                "sort_order": country_row[4],
                "calling_codes": [],
            }
            ordered_country_ids.append(country_id)

        if country_row[5] is not None:
            countries_by_id[country_id]["calling_codes"].append(
                {
                    "id": country_row[5],
                    "calling_code": country_row[6],
                    "is_primary": country_row[7],
                    "sort_order": country_row[8],
                }
            )

    countries = [countries_by_id[country_id] for country_id in ordered_country_ids]

    return {
        "countries": countries,
        "total_country_count": len(countries),
    }
