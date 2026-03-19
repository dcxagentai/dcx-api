"""
CONTEXT:
This file enforces Postgres-backed public-route rate limits for the DCX email-signup flow.
It exists so signup, OTP verify, and OTP resend routes can apply per-IP request budgets
without relying on in-memory counters that break across processes or deployments.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from dcx_storage.db_config import DB_CONFIG


def enforce_public_route_rate_limit_capability(
    route_key: str,
    client_ip: str,
    max_requests: int,
    window_ms: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - route_key identifies one public route family such as users_signup_email.
        - client_ip is the client address observed at the HTTP boundary.
        - max_requests and window_ms describe the allowed per-window request budget.
      postconditions:
        - Records one rate-limit hit for the current route/ip window.
        - Raises a stable error when the current window budget has already been exceeded.
      side_effects:
        - writes to stephen_dcx_public_route_rate_limits
      idempotent: false
      retry_safe: true
      async: false
      idempotency_key: public_route_rate_limit:{route_key}:{client_ip}:{window_start_ts_ms}
      locks:
        - postgres transaction-scoped advisory lock on route_key plus client_ip plus current window
      contention_strategy: serialize concurrent updates for the same route/ip/window, then increment one shared row

    NARRATIVE:
      WHY this exists:
        - Public signup-style flows need a lightweight, shared abuse brake before expensive DB or provider work happens.
      WHEN TO USE it:
        - Use it at the start of public signup, verify, and resend routes.
      WHEN NOT TO USE it:
        - Do not use it as the only abuse defense; pair it with per-email challenge cooldowns and attempt budgets.
      WHAT CAN GO WRONG:
        - Missing schema or DB connectivity will fail closed.
      WHAT COMES NEXT:
        - The route can continue to capability execution only when the budget is still open.

    TESTS:
      - first_hit_creates_window_row
      - repeated_hit_increments_existing_window_row
      - over_budget_hit_raises_rate_limit_error

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_EXCEEDED:
          suggested_action: Wait a little and retry the request.
          common_causes:
            - too many requests from one IP in the active time window
          recovery_steps:
            - Pause briefly.
            - Retry once the window rolls forward.
          retry_safe: true
      - API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_PERSISTENCE_FAILED:
          suggested_action: Confirm database health before retrying the public route.
          common_causes:
            - database unavailable
            - rate-limit table missing
          recovery_steps:
            - Verify schema application.
            - Retry when the database is healthy.
          retry_safe: true

    CODE:
    """
    normalized_client_ip = client_ip.strip() if isinstance(client_ip, str) else ""
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()
    window_start_ts_ms = now_ts_ms - (now_ts_ms % window_ms)

    if normalized_client_ip == "":
        normalized_client_ip = "unknown"

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"{route_key}:{normalized_client_ip}:{window_start_ts_ms}",),
                )
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_public_route_rate_limits (
                        route_key,
                        client_ip,
                        window_started_at_ts_ms,
                        request_count,
                        last_seen_at_ts_ms,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (route_key, client_ip, window_started_at_ts_ms) DO UPDATE
                    SET
                        request_count = stephen_dcx_public_route_rate_limits.request_count + 1,
                        last_seen_at_ts_ms = EXCLUDED.last_seen_at_ts_ms,
                        updated_at_ts_ms = EXCLUDED.updated_at_ts_ms
                    RETURNING request_count
                    """,
                    (
                        route_key,
                        normalized_client_ip,
                        window_start_ts_ms,
                        1,
                        now_ts_ms,
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                request_count = cursor.fetchone()[0]
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_PERSISTENCE_FAILED") from exc

    if request_count > max_requests:
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_RATE_LIMIT_EXCEEDED")

    return {
        "route_key": route_key,
        "client_ip": normalized_client_ip,
        "window_started_at_ts_ms": window_start_ts_ms,
        "request_count": request_count,
        "max_requests": max_requests,
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
