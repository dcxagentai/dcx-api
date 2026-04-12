"""
CONTEXT:
This file reads the currently allowed public signup source paths for the DCX public email-signup
flow. It exists so signup attribution can trust the same published route truth the public site uses,
rather than drifting behind hardcoded landing-page lists every time marketing or admin publishes new
localized category and article pages.
"""

from __future__ import annotations

from typing import Callable

from content.pages.read_dcx_public_live_content_pages_bundle import (
    read_dcx_public_live_content_pages_bundle,
)


PUBLIC_EMAIL_SIGNUP_STATIC_ALLOWED_ROOT_PATHS = {
    "/",
    "/en/",
    "/es/",
    "/fr/",
    "/de/",
    "/landing-page-1",
    "/es/pagina-1",
}


def read_allowed_public_email_signup_page_paths(
    read_public_live_content_pages_bundle: Callable[[], dict[str, list[dict[str, object]]]] | None = None,
) -> set[str]:
    """
    CONTRACT:
      preconditions:
        - The public content bundle reader is available.
      postconditions:
        - Returns a set of normalized same-origin public paths that are valid signup attribution
          sources.
        - Always includes the localized homepage roots and any legacy landing routes we still accept.
        - Adds currently published category and article paths for every live localized content page.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The signup form now appears on live content pages as well as the homepage, so allowed source
          paths should grow with published content instead of requiring code or environment edits.
      WHEN TO USE it:
        - Use it when validating `signup_page_url` on the public signup boundary.
      WHEN NOT TO USE it:
        - Do not use it as a generic public sitemap reader or as the source of truth for allowed
          browser origins.
      WHAT CAN GO WRONG:
        - If the published content bundle cannot be read, we should fail closed rather than accept
          arbitrary same-origin paths.
      WHAT COMES NEXT:
        - The normalized path set can be handed to the URL-normalization helper that already strips
          query strings and fragments from the browser-submitted signup page URL.

    TESTS:
      - returns_static_root_paths_when_no_content_pages_exist
      - adds_live_category_and_article_paths_from_published_content_bundle
      - deduplicates_repeated_category_paths
      - raises_stable_error_when_bundle_reader_fails

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_ALLOWED_PATHS_UNAVAILABLE:
          suggested_action: Retry the signup flow from the official DCX site once the backend is healthy.
          common_causes:
            - database connectivity failure
            - published content bundle reader failure
          recovery_steps:
            - Check backend database health.
            - Retry the signup request after the service recovers.
          retry_safe: true

    CODE:
    """
    read_bundle = read_public_live_content_pages_bundle or read_dcx_public_live_content_pages_bundle

    try:
        published_bundle = read_bundle()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_ALLOWED_PATHS_UNAVAILABLE") from exc

    allowed_paths = set(PUBLIC_EMAIL_SIGNUP_STATIC_ALLOWED_ROOT_PATHS)

    for language_code, language_pages in published_bundle.items():
        normalized_language_root = _normalize_public_signup_path(f"/{language_code}/")
        allowed_paths.add(normalized_language_root)

        for page in language_pages:
            category_slug = str(page.get("category_slug") or "").strip().strip("/")
            page_slug = str(page.get("page_slug") or "").strip().strip("/")

            if category_slug == "" or page_slug == "":
                continue

            allowed_paths.add(
                _normalize_public_signup_path(f"/{language_code}/{category_slug}")
            )
            allowed_paths.add(
                _normalize_public_signup_path(f"/{language_code}/{category_slug}/{page_slug}")
            )

    return allowed_paths


def _normalize_public_signup_path(route_path: str) -> str:
    """
    CONTRACT:
      preconditions:
        - route_path is one path-like string without query string or fragment.
      postconditions:
        - Returns one normalized path while preserving explicit locale roots like `/es/`.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    CODE:
    """
    if route_path in {"", "/"}:
        return "/"

    if route_path.rstrip("/") in {"/en", "/es", "/fr", "/de"}:
        return f"{route_path.rstrip('/')}/"

    return route_path.rstrip("/")
