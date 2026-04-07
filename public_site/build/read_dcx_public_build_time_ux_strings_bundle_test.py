"""
CONTEXT:
This file verifies the build-time live public UX-string bundle capability.
It keeps the real public static-build content path secure before `dcx_public` starts relying on it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from public_site.build.read_dcx_public_build_time_ux_strings_bundle import (
    read_dcx_public_build_time_ux_strings_bundle_capability,
)


def test_returns_live_public_bundle_for_matching_token() -> None:
    with patch(
        "public_site.build.read_dcx_public_build_time_ux_strings_bundle.validate_dcx_public_build_api_token_capability"
    ) as validate_token_mock, patch(
        "public_site.build.read_dcx_public_build_time_ux_strings_bundle.read_live_dcx_public_ux_strings_bundle",
        return_value={
            "en": {"home": {"meta_title": "DCX | Public queue"}},
            "es": {"home": {"meta_title": "DCX | Cola publica"}},
            "fr": {"home": {"meta_title": "DCX | File publique"}},
            "de": {"home": {"meta_title": "DCX | Offentliche Warteliste"}},
        },
    ):
        payload = read_dcx_public_build_time_ux_strings_bundle_capability(
            "top-secret-build-token"
        )

    validate_token_mock.assert_called_once_with("top-secret-build-token")
    assert payload["en"]["home"]["meta_title"] == "DCX | Public queue"


def test_raises_when_token_validation_fails() -> None:
    with patch(
        "public_site.build.read_dcx_public_build_time_ux_strings_bundle.validate_dcx_public_build_api_token_capability",
        side_effect=RuntimeError("API_PUBLIC_BUILD_TOKEN_INVALID"),
    ):
        with pytest.raises(RuntimeError, match="API_PUBLIC_BUILD_TOKEN_INVALID"):
            read_dcx_public_build_time_ux_strings_bundle_capability("wrong-token")


def test_raises_when_live_public_bundle_reader_fails() -> None:
    with patch(
        "public_site.build.read_dcx_public_build_time_ux_strings_bundle.validate_dcx_public_build_api_token_capability"
    ), patch(
        "public_site.build.read_dcx_public_build_time_ux_strings_bundle.read_live_dcx_public_ux_strings_bundle",
        side_effect=RuntimeError("API_PUBLIC_UX_STRINGS_DB_UNAVAILABLE"),
    ):
        with pytest.raises(RuntimeError, match="API_PUBLIC_UX_STRINGS_DB_UNAVAILABLE"):
            read_dcx_public_build_time_ux_strings_bundle_capability("top-secret-build-token")
