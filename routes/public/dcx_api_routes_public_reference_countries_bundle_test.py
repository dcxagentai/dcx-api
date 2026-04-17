from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from dcx_api_app import app
import routes.public.dcx_api_routes_public_reference_countries_bundle as public_reference_countries_routes

client = TestClient(app)


def test_public_reference_countries_bundle_route_returns_bundle() -> None:
    with patch.object(
        public_reference_countries_routes,
        "read_active_dcx_reference_countries_bundle",
        return_value={
            "countries": [
                {
                    "id": 10,
                    "country_code_alpha2": "ES",
                    "default_display_name": "Spain",
                    "flag_asset_key": "es",
                    "sort_order": 10,
                    "calling_codes": [
                        {
                            "id": 101,
                            "calling_code": "+34",
                            "is_primary": True,
                            "sort_order": 10,
                        }
                    ],
                }
            ],
            "total_country_count": 1,
        },
    ):
        response = client.get("/public/reference/countries-bundle")
        payload = response.json()

    assert response.status_code == 200
    assert payload == {
        "ok": True,
        "data": {
            "countries": [
                {
                    "id": 10,
                    "country_code_alpha2": "ES",
                    "default_display_name": "Spain",
                    "flag_asset_key": "es",
                    "sort_order": 10,
                    "calling_codes": [
                        {
                            "id": 101,
                            "calling_code": "+34",
                            "is_primary": True,
                            "sort_order": 10,
                        }
                    ],
                }
            ],
            "total_country_count": 1,
        },
        "context": {
            "surface": "public_reference",
            "view": "countries_bundle",
        },
    }


def test_public_reference_countries_bundle_route_returns_error_wrapper_on_failure() -> None:
    with patch.object(
        public_reference_countries_routes,
        "read_active_dcx_reference_countries_bundle",
        side_effect=RuntimeError("API_DCX_REFERENCE_COUNTRIES_READ_FAILED"),
    ):
        response = client.get("/public/reference/countries-bundle")
        payload = response.json()

    assert response.status_code == 500
    assert payload == {
        "ok": False,
        "error": {
            "code": "API_DCX_REFERENCE_COUNTRIES_READ_FAILED",
            "message": "We could not load the countries reference bundle just now.",
            "suggested_action": "Retry after the backend countries reference route is healthy.",
        },
    }
