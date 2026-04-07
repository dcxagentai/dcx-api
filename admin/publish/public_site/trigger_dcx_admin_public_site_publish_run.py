"""
CONTEXT:
This file triggers one Cloudflare Pages publish request for the DCX public site.
It exists so the admin workspace can ask the static public frontend to rebuild after live public
UX-string edits land in Postgres and the build-time API bundle has become the source of truth.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

import httpx
import psycopg2

from routes.users.dcx_api_routes_users_support import read_dcx_runtime_environment
from storage.db_config import DB_CONFIG

DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY = "dcx_public"


def trigger_dcx_admin_public_site_publish_run_capability(
    triggered_by_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    post_to_deploy_hook: Callable[..., Any] | None = None,
    current_timestamp_ms: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - triggered_by_user_id identifies the admin user requesting the publish.
        - The configured database is reachable.
        - `stephen_dcx_public_content_publish_state` exists.
        - In production/staging, `DCX_PUBLIC_CLOUDFLARE_PAGES_DEPLOY_HOOK_URL` is configured on the backend.
      postconditions:
        - Records one attempted publish trigger for the `dcx_public` surface.
        - In local/development, records that a manual local rebuild is needed instead of calling Cloudflare.
        - In hosted environments, calls the configured Cloudflare Pages deploy hook exactly once.
        - Marks the publish state as `trigger_accepted` when the deploy hook returns a 2xx response.
        - Marks the publish state as `failed` when the deploy hook is rejected or unavailable.
      side_effects:
        - writes the latest attempted/accepted publish metadata to `stephen_dcx_public_content_publish_state`
        - performs one outbound HTTP POST to the configured Cloudflare Pages deploy hook in hosted environments only
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: last write wins for publish-state metadata because repeated publish requests are operationally acceptable

    NARRATIVE:
      WHY this exists:
        - The admin workflow needs one deliberate publish button after the public site switched to
          build-time reads from the live backend/database.
      WHEN TO USE it:
        - Use it when admin users want Cloudflare Pages to rebuild the public site from the current
          live public UX strings.
      WHEN NOT TO USE it:
        - Do not use it for app/admin content because those surfaces already read from the API directly.
      WHAT CAN GO WRONG:
        - The deploy hook environment variable can be missing in hosted environments.
        - Cloudflare can reject or fail to accept the deploy request in hosted environments.
        - The publish-state table can be missing before its SQL is applied.
      WHAT COMES NEXT:
        - The status reader can show the accepted publish timestamp and whether new DB edits have
          accumulated since the last accepted trigger.

    TESTS:
      - returns_trigger_accepted_result_when_hook_post_succeeds
      - returns_local_manual_rebuild_result_in_local_development
      - raises_clear_error_when_deploy_hook_url_is_missing
      - raises_clear_error_when_hook_post_fails

    ERRORS:
      - API_DCX_ADMIN_PUBLIC_SITE_DEPLOY_HOOK_NOT_CONFIGURED:
          suggested_action: Set DCX_PUBLIC_CLOUDFLARE_PAGES_DEPLOY_HOOK_URL on the backend and retry.
          common_causes:
            - missing Render environment variable
            - typo in env var name
          recovery_steps:
            - Add the deploy hook URL to the backend environment.
            - Redeploy the backend.
            - Retry the publish request.
          retry_safe: true
          what_changed: no publish request was sent
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_TRIGGER_FAILED:
          suggested_action: Retry after Cloudflare hook/network health is restored.
          common_causes:
            - Cloudflare deploy hook unavailable
            - network timeout
            - non-2xx deploy hook response
          recovery_steps:
            - Confirm the deploy hook URL is valid.
            - Retry once the hook/network is healthy.
          retry_safe: true
          what_changed: publish attempt metadata was recorded, but the accepted publish timestamp was not advanced
          rollback_needed: false
          rollback_operation: none

    CODE:
    """
    if not isinstance(triggered_by_user_id, int) or triggered_by_user_id <= 0:
        raise RuntimeError("API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_TRIGGER_FAILED")

    connect = connect_to_database or psycopg2.connect
    post_request = post_to_deploy_hook or httpx.post
    read_now_ms = current_timestamp_ms or (lambda: int(time.time() * 1000))
    runtime_environment = read_dcx_runtime_environment()

    attempted_at_ts_ms = read_now_ms()

    def write_publish_state(
        *,
        last_attempted_publish_at_ts_ms: int,
        last_attempted_publish_by_user_id: int,
        last_publish_status: str,
        last_publish_message: str,
        last_successful_publish_at_ts_ms: int | None = None,
        last_successful_publish_by_user_id: int | None = None,
    ) -> None:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_public_content_publish_state (
                        surface_key,
                        last_publish_status
                    )
                    VALUES (%s, %s)
                    ON CONFLICT (surface_key) DO NOTHING
                    """,
                    (
                        DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY,
                        "never_published",
                    ),
                )

                cursor.execute(
                    """
                    UPDATE stephen_dcx_public_content_publish_state
                    SET
                        last_successful_publish_at_ts_ms = COALESCE(%s, last_successful_publish_at_ts_ms),
                        last_successful_publish_by_user_id = COALESCE(%s, last_successful_publish_by_user_id),
                        last_attempted_publish_at_ts_ms = %s,
                        last_attempted_publish_by_user_id = %s,
                        last_publish_status = %s,
                        last_publish_message = %s,
                        updated_at_ts_ms = (EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::BIGINT
                    WHERE surface_key = %s
                    """,
                    (
                        last_successful_publish_at_ts_ms,
                        last_successful_publish_by_user_id,
                        last_attempted_publish_at_ts_ms,
                        last_attempted_publish_by_user_id,
                        last_publish_status,
                        last_publish_message,
                        DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY,
                    ),
                )

    write_publish_state(
        last_attempted_publish_at_ts_ms=attempted_at_ts_ms,
        last_attempted_publish_by_user_id=triggered_by_user_id,
        last_publish_status="deploy_requested",
        last_publish_message=(
            "Local public rebuild request started."
            if runtime_environment in {"local", "development"}
            else "Cloudflare Pages deploy hook request started."
        ),
    )

    if runtime_environment in {"local", "development"}:
        write_publish_state(
            last_attempted_publish_at_ts_ms=attempted_at_ts_ms,
            last_attempted_publish_by_user_id=triggered_by_user_id,
            last_publish_status="local_manual_rebuild_required",
            last_publish_message=(
                "Local mode does not call Cloudflare. Run npm run dev or npm run build in dcx_public against the local API to refresh the public site."
            ),
        )
        return {
            "surface_key": DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY,
            "triggered_by_user_id": triggered_by_user_id,
            "accepted_publish_at_ts_ms": attempted_at_ts_ms,
            "last_publish_status": "local_manual_rebuild_required",
            "last_publish_message": (
                "Local mode does not call Cloudflare. Run npm run dev or npm run build in dcx_public against the local API to refresh the public site."
            ),
        }

    deploy_hook_url = os.getenv("DCX_PUBLIC_CLOUDFLARE_PAGES_DEPLOY_HOOK_URL", "").strip()
    if deploy_hook_url == "":
        raise RuntimeError("API_DCX_ADMIN_PUBLIC_SITE_DEPLOY_HOOK_NOT_CONFIGURED")

    try:
        deploy_hook_response = post_request(
            deploy_hook_url,
            timeout=20.0,
        )
        status_code = int(getattr(deploy_hook_response, "status_code", 0))

        if status_code < 200 or status_code >= 300:
            raise RuntimeError(
                f"API_DCX_ADMIN_PUBLIC_SITE_DEPLOY_HOOK_REJECTED:{status_code}"
            )
    except Exception as exc:
        failure_message = "Cloudflare Pages deploy hook request failed."
        if isinstance(exc, RuntimeError) and str(exc).startswith(
            "API_DCX_ADMIN_PUBLIC_SITE_DEPLOY_HOOK_REJECTED:"
        ):
            rejected_status_code = str(exc).split(":", 1)[1]
            failure_message = (
                f"Cloudflare Pages deploy hook rejected the request with status {rejected_status_code}."
            )

        write_publish_state(
            last_attempted_publish_at_ts_ms=attempted_at_ts_ms,
            last_attempted_publish_by_user_id=triggered_by_user_id,
            last_publish_status="failed",
            last_publish_message=failure_message,
        )
        raise RuntimeError("API_DCX_ADMIN_PUBLIC_SITE_PUBLISH_TRIGGER_FAILED") from exc

    accepted_publish_at_ts_ms = read_now_ms()
    write_publish_state(
        last_successful_publish_at_ts_ms=accepted_publish_at_ts_ms,
        last_successful_publish_by_user_id=triggered_by_user_id,
        last_attempted_publish_at_ts_ms=accepted_publish_at_ts_ms,
        last_attempted_publish_by_user_id=triggered_by_user_id,
        last_publish_status="trigger_accepted",
        last_publish_message="Cloudflare Pages deploy hook accepted the publish request.",
    )

    return {
        "surface_key": DCX_ADMIN_PUBLIC_SITE_SURFACE_KEY,
        "triggered_by_user_id": triggered_by_user_id,
        "accepted_publish_at_ts_ms": accepted_publish_at_ts_ms,
        "last_publish_status": "trigger_accepted",
        "last_publish_message": "Cloudflare Pages deploy hook accepted the publish request.",
    }
