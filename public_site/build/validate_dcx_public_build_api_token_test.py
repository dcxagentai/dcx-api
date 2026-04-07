"""
CONTEXT:
This file verifies the shared backend build-token validator for `dcx_public` static-generation
requests.
It keeps the secure machine-to-machine gate consistent as more public build-time routes are added.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from public_site.build.validate_dcx_public_build_api_token import (
    validate_dcx_public_build_api_token_capability,
)


def test_returns_none_for_matching_token() -> None:
    with patch.dict(
        "os.environ",
        {"DCX_PUBLIC_BUILD_API_TOKEN": "top-secret-build-token"},
        clear=False,
    ):
        result = validate_dcx_public_build_api_token_capability("top-secret-build-token")

    assert result is None


def test_raises_when_backend_build_token_missing() -> None:
    with patch.dict("os.environ", {"DCX_PUBLIC_BUILD_API_TOKEN": ""}, clear=False):
        with pytest.raises(RuntimeError, match="API_PUBLIC_BUILD_TOKEN_NOT_CONFIGURED"):
            validate_dcx_public_build_api_token_capability("top-secret-build-token")


def test_raises_when_request_token_missing() -> None:
    with patch.dict(
        "os.environ",
        {"DCX_PUBLIC_BUILD_API_TOKEN": "top-secret-build-token"},
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="API_PUBLIC_BUILD_TOKEN_REQUIRED"):
            validate_dcx_public_build_api_token_capability(None)


def test_raises_when_request_token_invalid() -> None:
    with patch.dict(
        "os.environ",
        {"DCX_PUBLIC_BUILD_API_TOKEN": "top-secret-build-token"},
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="API_PUBLIC_BUILD_TOKEN_INVALID"):
            validate_dcx_public_build_api_token_capability("wrong-token")
