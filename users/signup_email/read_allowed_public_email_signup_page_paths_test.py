"""
CONTEXT:
This file falsifies the allowed public signup path reader for the DCX public email-signup flow. It
keeps the dynamic published-route allowlist honest next to the capability that derives it.
"""

import pytest

from users.signup_email.read_allowed_public_email_signup_page_paths import (
    read_allowed_public_email_signup_page_paths,
)


def test_returns_static_root_paths_when_no_content_pages_exist() -> None:
    allowed_paths = read_allowed_public_email_signup_page_paths(
        read_public_live_content_pages_bundle=lambda: {}
    )

    assert "/" in allowed_paths
    assert "/en/" in allowed_paths
    assert "/es/" in allowed_paths
    assert "/fr/" in allowed_paths
    assert "/de/" in allowed_paths


def test_adds_live_category_and_article_paths_from_published_content_bundle() -> None:
    allowed_paths = read_allowed_public_email_signup_page_paths(
        read_public_live_content_pages_bundle=lambda: {
            "en": [
                {"category_slug": "insights", "page_slug": "live-test-page"},
            ],
            "es": [
                {"category_slug": "pensamientos", "page_slug": "pagina-de-prueba"},
            ],
        }
    )

    assert "/en/insights" in allowed_paths
    assert "/en/insights/live-test-page" in allowed_paths
    assert "/es/pensamientos" in allowed_paths
    assert "/es/pensamientos/pagina-de-prueba" in allowed_paths


def test_deduplicates_repeated_category_paths() -> None:
    allowed_paths = read_allowed_public_email_signup_page_paths(
        read_public_live_content_pages_bundle=lambda: {
            "en": [
                {"category_slug": "insights", "page_slug": "first-page"},
                {"category_slug": "insights", "page_slug": "second-page"},
            ],
        }
    )

    assert list(path for path in allowed_paths if path == "/en/insights") == ["/en/insights"]


def test_raises_stable_error_when_bundle_reader_fails() -> None:
    def _raise_bundle_failure() -> dict[str, list[dict[str, object]]]:
        raise RuntimeError("db unavailable")

    with pytest.raises(RuntimeError, match="API_PUBLIC_EMAIL_SIGNUP_ALLOWED_PATHS_UNAVAILABLE"):
        read_allowed_public_email_signup_page_paths(
            read_public_live_content_pages_bundle=_raise_bundle_failure
        )
