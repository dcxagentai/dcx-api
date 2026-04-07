"""
CONTEXT:
This file verifies the build-time public API proof capability.
It keeps the token-gated build proof route honest before the real public build pipeline depends on it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from public_site.build.read_dcx_public_build_time_api_test_payload import (
    read_dcx_public_build_time_api_test_payload_capability,
)


def test_returns_build_time_test_payload_for_matching_token() -> None:
    with patch.dict(
        "os.environ",
        {
            "DCX_PUBLIC_BUILD_API_TOKEN": "top-secret-build-token",
            "DCX_ENVIRONMENT": "production",
        },
        clear=False,
    ):
        payload = read_dcx_public_build_time_api_test_payload_capability(
            "top-secret-build-token"
        )

    assert (
        payload["build_test_message"]
        == "DCX public Astro builds can securely fetch from dcx_api during static generation."
    )
    assert payload["backend_runtime_environment"] == "production"
    assert isinstance(payload["issued_at_ts_ms"], int)


def test_raises_when_backend_build_token_missing() -> None:
    with patch.dict("os.environ", {"DCX_PUBLIC_BUILD_API_TOKEN": ""}, clear=False):
        with pytest.raises(RuntimeError, match="API_PUBLIC_BUILD_TOKEN_NOT_CONFIGURED"):
            read_dcx_public_build_time_api_test_payload_capability("top-secret-build-token")


def test_raises_when_request_token_missing() -> None:
    with patch.dict(
        "os.environ",
        {"DCX_PUBLIC_BUILD_API_TOKEN": "top-secret-build-token"},
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="API_PUBLIC_BUILD_TOKEN_REQUIRED"):
            read_dcx_public_build_time_api_test_payload_capability(None)


def test_raises_when_request_token_invalid() -> None:
    with patch.dict(
        "os.environ",
        {"DCX_PUBLIC_BUILD_API_TOKEN": "top-secret-build-token"},
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="API_PUBLIC_BUILD_TOKEN_INVALID"):
            read_dcx_public_build_time_api_test_payload_capability("wrong-token")
