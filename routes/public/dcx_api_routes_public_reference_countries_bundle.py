"""
CONTEXT:
This file exposes the active DCX countries reference bundle over one public read route.
It exists so frontend surfaces can fetch a shared global countries model from the backend
instead of embedding divergent country metadata in each app.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from countries.read_active_dcx_reference_countries_bundle import (
    read_active_dcx_reference_countries_bundle,
)

dcx_api_routes_public_reference_countries_bundle_router = APIRouter(
    prefix="/public/reference",
    tags=["public_reference"],
)


@dcx_api_routes_public_reference_countries_bundle_router.get(
    "/countries-bundle",
    response_model=None,
)
def get_dcx_public_reference_countries_bundle():
    """
    CONTRACT:
      preconditions:
        - The backend can reach the configured database.
      postconditions:
        - Returns one canonical success wrapper containing the active countries reference bundle.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Global UX surfaces need one reusable countries read contract before trade-region and
          market-organization flows expand.
      WHEN TO USE it:
        - Use it from frontend country pickers and reference-data reads.
      WHEN NOT TO USE it:
        - Do not use it for phone verification or ownership checks.
      WHAT CAN GO WRONG:
        - Database-backed reads can fail.
      WHAT COMES NEXT:
        - Future flows can reuse the same bundle for trade geography and localized country labels.

    TESTS:
      - public_reference_countries_bundle_route_returns_bundle
      - public_reference_countries_bundle_route_returns_error_wrapper_on_failure

    ERRORS:
      - API_DCX_REFERENCE_COUNTRIES_READ_FAILED:
          suggested_action: Retry after the backend countries reference route is healthy.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database health.
            - Retry once the backend is stable.
          retry_safe: true

    CODE:
    """
    try:
        countries_bundle = read_active_dcx_reference_countries_bundle()
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_REFERENCE_COUNTRIES_READ_FAILED",
                    "message": "We could not load the countries reference bundle just now.",
                    "suggested_action": "Retry after the backend countries reference route is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": countries_bundle,
        "context": {
            "surface": "public_reference",
            "view": "countries_bundle",
        },
    }
