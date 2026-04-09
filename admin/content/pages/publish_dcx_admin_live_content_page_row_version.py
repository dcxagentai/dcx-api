"""
CONTEXT:
This file publishes one live content-page row version for the DCX admin content surface.
It exists so the admin editor can keep publish as one explicit workflow action on top of the
shared immutable page-save model.
"""

from __future__ import annotations

from typing import Any, Callable

from admin.content.pages.save_dcx_admin_live_content_page_row_version import (
    save_dcx_admin_live_content_page_row_version_capability,
)


def publish_dcx_admin_live_content_page_row_version_capability(
    target_page_id: int,
    next_category_key: str,
    next_page_title: str,
    next_page_lede: str,
    next_page_body_markdown: str,
    next_meta_title: str,
    next_meta_description: str,
    next_page_slug: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - The target page exists as one current live row.
        - The candidate publish content is valid for the shared page save capability.
      postconditions:
        - Saves one immutable live row version with `publication_status = published`.
        - Stamps `published_at_ts_ms` with the current wall-clock time.
      side_effects:
        - updates one current live content-page row to `is_live = false`
        - inserts one new published live content-page row when content changed
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Publishing is one clearer workflow action than passing raw status strings through every frontend call.
      WHEN TO USE it:
        - Use it from the admin page editor `Publish` action only.
      WHEN NOT TO USE it:
        - Do not use it for draft autosave.
      WHAT CAN GO WRONG:
        - The underlying save capability can reject invalid content or stale ids.
      WHAT COMES NEXT:
        - The public-site publish-status flow can pick up this newly published row for deploy.

    TESTS:
      - covered_indirectly_by_content_page_publish_route_tests

    ERRORS:
      - inherits_shared_page_save_errors:
          suggested_action: Follow the surfaced save/publish error and retry from the current live row.
          common_causes:
            - stale page row
            - invalid content
            - database unavailable
          recovery_steps:
            - Refresh the editor.
            - Correct the content if needed.
            - Retry once the backend is healthy.
          retry_safe: true

    CODE:
    """
    from time import time

    return save_dcx_admin_live_content_page_row_version_capability(
        target_page_id=target_page_id,
        next_category_key=next_category_key,
        next_page_title=next_page_title,
        next_page_lede=next_page_lede,
        next_page_body_markdown=next_page_body_markdown,
        next_meta_title=next_meta_title,
        next_meta_description=next_meta_description,
        next_page_slug=next_page_slug,
        next_publication_status="published",
        next_published_at_ts_ms=int(time() * 1000),
        connect_to_database=connect_to_database,
    )
