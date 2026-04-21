"""
CONTEXT:
This file prepares one DCX newsletter send row, recipient snapshot set, and tracked-link set.
It exists so the admin workspace can stage real newsletter send mechanics before the background
Resend dispatcher is connected.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any, Callable

import psycopg2

from content.newsletter_sends.build_dcx_emails_sends_links_from_newsletter_markdown import (
    build_dcx_emails_sends_links_from_newsletter_markdown,
)
from storage.db_config import DB_CONFIG


def prepare_dcx_admin_newsletter_send_capability(
    authenticated_admin_user_id: int,
    email_key: str,
    language_code: str,
    scheduled_send_at_ts_ms: int | None,
    send_audience_scope: str = "all",
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
    tracking_token_provider: Callable[[], str] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_admin_user_id identifies one current admin/dev user.
        - email_key and language_code identify one current live newsletter row.
        - scheduled_send_at_ts_ms is either null or one unix-milliseconds timestamp.
        - send_audience_scope is one of `all`, `admins`, or `devs`.
        - The configured database is reachable.
      postconditions:
        - Creates one new row in `stephen_dcx_emails_sends`.
        - Creates one snapshot row in `stephen_dcx_emails_sends_recipients` for each relevant user inside the selected audience scope.
        - Creates one row in `stephen_dcx_emails_sends_links` for each unique outbound link in each resolved newsletter variant used by the send.
        - Only marks users as `send` candidates when a live newsletter row exists in their preferred language (or in English when no preference exists).
        - Skips newsletter candidates whose current preference blocks newsletters or whose email address is actively suppressed for newsletter/all-email sends.
        - Returns one summary of the prepared send.
      side_effects:
        - inserts one prepared newsletter send row
        - inserts recipient snapshot rows
        - inserts tracked link rows
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - transaction-scoped advisory lock on newsletter key plus scheduled send timestamp
      contention_strategy: serialize competing send preparation attempts for the same newsletter/timestamp combination while still allowing deliberate distinct sends

    NARRATIVE:
      WHY this exists:
        - The client needs to see believable send mechanics before the actual dispatch worker exists.
      WHEN TO USE it:
        - Use it from the admin newsletter editor when an internal user chooses `prepare now` or `prepare scheduled send`.
      WHEN NOT TO USE it:
        - Do not use it for actual Resend delivery yet.
      WHAT CAN GO WRONG:
        - The selected newsletter can be missing.
        - The selected audience scope can be invalid.
        - Users may be blocked because the newsletter has not yet been translated into their preferred language.
        - Database writes can fail.
      WHAT COMES NEXT:
        - Later a dispatcher will pick up these scheduled rows and call Resend.

    TESTS:
      - creates_send_row_recipient_snapshots_and_link_rows
      - filters_recipients_to_admin_scope_when_requested
      - skips_users_when_newsletter_translation_is_missing_for_their_preferred_language
      - skips_users_when_newsletter_suppression_is_active
      - raises_clear_error_when_source_newsletter_missing

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_SEND_INVALID:
          suggested_action: Retry from one valid newsletter route and choose a valid schedule time.
            common_causes:
              - blank email key
              - blank language code
              - invalid admin user id
              - invalid send audience scope
          recovery_steps:
            - Reopen the newsletter from the catalog.
            - Retry with the current live row.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_NEWSLETTER_SEND_SOURCE_NOT_FOUND:
          suggested_action: Refresh the newsletter catalog and reopen the current live row before preparing the send.
          common_causes:
            - stale newsletter route
            - live row no longer exists
          recovery_steps:
            - Reload the newsletters catalog.
            - Retry from the live newsletter row.
          retry_safe: true
          what_changed: nothing was created
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_NEWSLETTER_SEND_PREPARE_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - insert failure
            - inconsistent newsletter translation state
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the target send row before retrying

    CODE:
    """
    normalized_email_key = email_key.strip()
    normalized_language_code = language_code.strip().lower()
    normalized_send_audience_scope = send_audience_scope.strip().lower()
    if (
        authenticated_admin_user_id <= 0
        or normalized_email_key == ""
        or normalized_language_code == ""
        or normalized_send_audience_scope not in {"all", "admins", "devs"}
    ):
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_SEND_INVALID")

    current_timestamp_ms = (
        current_timestamp_ms_provider() if current_timestamp_ms_provider else _read_current_timestamp_ms()
    )
    normalized_scheduled_send_at_ts_ms = (
        scheduled_send_at_ts_ms
        if isinstance(scheduled_send_at_ts_ms, int) and scheduled_send_at_ts_ms > 0
        else current_timestamp_ms
    )
    build_tracking_token = tracking_token_provider or _build_tracking_token
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (
                        f"dcx_newsletter_send_prepare:{normalized_email_key}:{normalized_scheduled_send_at_ts_ms}",
                    ),
                )
                cursor.execute(
                    """
                    SELECT
                        e.id,
                        e.email_key,
                        e.language_id,
                        e.email_subject,
                        e.email_body,
                        l.language_code
                    FROM stephen_dcx_emails AS e
                    INNER JOIN stephen_dcx_languages AS l
                      ON l.id = e.language_id
                    WHERE e.email_type = 'newsletter'
                      AND e.is_live = TRUE
                      AND e.email_key = %s
                      AND l.language_code = %s
                    LIMIT 1
                    """,
                    (normalized_email_key, normalized_language_code),
                )
                source_email_row = cursor.fetchone()
                if source_email_row is None:
                    raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_SEND_SOURCE_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT
                        e.id,
                        e.language_id,
                        e.email_subject,
                        e.email_body,
                        l.language_code
                    FROM stephen_dcx_emails AS e
                    INNER JOIN stephen_dcx_languages AS l
                      ON l.id = e.language_id
                    WHERE e.email_type = 'newsletter'
                      AND e.is_live = TRUE
                      AND e.email_key = %s
                    ORDER BY e.id ASC
                    """,
                    (normalized_email_key,),
                )
                variant_rows = cursor.fetchall()
                variant_by_language_id = {row[1]: row for row in variant_rows}
                english_variant = next(
                    (variant_row for variant_row in variant_rows if variant_row[4] == "en"),
                    None,
                )
                default_variant = english_variant or source_email_row

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_emails_sends (
                        source_email_id,
                        email_key_snapshot,
                        send_kind,
                        send_status,
                        send_audience_type,
                        scheduled_send_at_ts_ms,
                        created_by_user_id,
                        updated_by_user_id,
                        send_summary_json
                    )
                    VALUES (%s, %s, 'newsletter', 'scheduled', 'newsletters', %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        source_email_row[0],
                        normalized_email_key,
                        normalized_scheduled_send_at_ts_ms,
                        authenticated_admin_user_id,
                        authenticated_admin_user_id,
                        json.dumps(
                            {
                                "send_audience_scope": normalized_send_audience_scope,
                            }
                        ),
                    ),
                )
                email_send_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT
                        user_row.id,
                        primary_email_contact_method.normalized_value,
                        primary_email_contact_method.is_verified,
                        user_row.preferred_language_id,
                        user_row.email_communication_preference,
                        user_row.account_status,
                        user_row.user_role,
                        EXISTS (
                            SELECT 1
                            FROM stephen_dcx_emails_suppressions AS suppression_row
                            WHERE suppression_row.is_active = TRUE
                              AND suppression_row.normalized_contact_value = primary_email_contact_method.normalized_value
                              AND suppression_row.suppression_scope IN ('newsletters', 'all_email')
                        ) AS has_newsletter_suppression
                    FROM stephen_dcx_users AS user_row
                    LEFT JOIN LATERAL (
                        SELECT
                            normalized_value,
                            is_verified
                        FROM stephen_dcx_users_contact_methods
                        WHERE user_id = user_row.id
                          AND contact_type = 'email'
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) primary_email_contact_method
                          ON TRUE
                    WHERE (
                        %s = 'all'
                        OR (%s = 'admins' AND user_row.user_role = 'admin')
                        OR (%s = 'devs' AND user_row.user_role = 'dev')
                    )
                    ORDER BY user_row.id ASC
                    """,
                    (
                        normalized_send_audience_scope,
                        normalized_send_audience_scope,
                        normalized_send_audience_scope,
                    ),
                )
                user_rows = cursor.fetchall()

                prepared_recipient_count = 0
                send_candidate_count = 0
                skipped_recipient_count = 0
                blocked_missing_translation_count = 0
                resolved_variant_rows: dict[int, tuple] = {}

                for user_row in user_rows:
                    resolved_variant = _read_resolved_newsletter_variant_for_user_row(
                        user_row=user_row,
                        variant_by_language_id=variant_by_language_id,
                        english_variant=english_variant,
                        default_variant=default_variant,
                    )
                    resolved_variant_rows[resolved_variant[0]] = resolved_variant
                    delivery_decision, failure_reason = _read_delivery_decision_for_user_row(
                        user_row=user_row,
                        resolved_variant=resolved_variant,
                        variant_by_language_id=variant_by_language_id,
                        english_variant=english_variant,
                    )
                    delivery_status = "pending" if delivery_decision == "send" else "skipped"
                    prepared_recipient_count += 1
                    if delivery_decision == "send":
                        send_candidate_count += 1
                    else:
                        skipped_recipient_count += 1
                        if failure_reason is not None and failure_reason.startswith("missing_translation:"):
                            blocked_missing_translation_count += 1

                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_emails_sends_recipients (
                            email_send_id,
                            user_id,
                            resolved_email_id,
                            recipient_email_snapshot,
                            recipient_language_id_snapshot,
                            resolved_language_id_snapshot,
                            email_communication_preference_snapshot,
                            delivery_decision,
                            delivery_status,
                            failure_reason
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            email_send_id,
                            user_row[0],
                            resolved_variant[0],
                            user_row[1],
                            user_row[3],
                            resolved_variant[1],
                            user_row[4],
                            delivery_decision,
                            delivery_status,
                            failure_reason,
                        ),
                    )

                tracked_link_count = 0
                for resolved_variant in resolved_variant_rows.values():
                    for link_row in build_dcx_emails_sends_links_from_newsletter_markdown(resolved_variant[3]):
                        cursor.execute(
                            """
                            INSERT INTO stephen_dcx_emails_sends_links (
                                email_send_id,
                                resolved_email_id,
                                original_url,
                                tracking_token,
                                link_label
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            RETURNING id
                            """,
                            (
                                email_send_id,
                                resolved_variant[0],
                                link_row["original_url"],
                                build_tracking_token(),
                                link_row["link_label"],
                            ),
                        )
                        cursor.fetchone()
                        tracked_link_count += 1

                send_summary = {
                    "send_audience_scope": normalized_send_audience_scope,
                    "prepared_recipient_count": prepared_recipient_count,
                    "send_candidate_count": send_candidate_count,
                    "skipped_recipient_count": skipped_recipient_count,
                    "blocked_missing_translation_count": blocked_missing_translation_count,
                    "tracked_link_count": tracked_link_count,
                }
                cursor.execute(
                    """
                    UPDATE stephen_dcx_emails_sends
                    SET send_summary_json = %s::jsonb,
                        updated_by_user_id = %s
                    WHERE id = %s
                    """,
                    (
                        json.dumps(send_summary),
                        authenticated_admin_user_id,
                        email_send_id,
                    ),
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_SEND_PREPARE_FAILED") from exc

    return {
        "email_send_id": email_send_id,
        "email_key": normalized_email_key,
        "send_status": "scheduled",
        "scheduled_send_at_ts_ms": normalized_scheduled_send_at_ts_ms,
        "send_audience_scope": normalized_send_audience_scope,
        "summary": send_summary,
    }


def _read_current_timestamp_ms() -> int:
    return int(time.time() * 1000)


def _build_tracking_token() -> str:
    return secrets.token_urlsafe(18)


def _read_resolved_newsletter_variant_for_user_row(
    user_row: tuple,
    variant_by_language_id: dict[int, tuple],
    english_variant: tuple | None,
    default_variant: tuple,
) -> tuple:
    preferred_language_id = user_row[3]
    if preferred_language_id is None:
        return english_variant or default_variant
    return variant_by_language_id.get(preferred_language_id) or default_variant


def _read_delivery_decision_for_user_row(
    user_row: tuple,
    resolved_variant: tuple,
    variant_by_language_id: dict[int, tuple],
    english_variant: tuple | None,
) -> tuple[str, str | None]:
    recipient_email = (user_row[1] or "").strip()
    primary_email_confirmed = bool(user_row[2])
    preferred_language_id = user_row[3]
    email_communication_preference = (user_row[4] or "").strip().lower()
    account_status = (user_row[5] or "").strip().lower()
    has_newsletter_suppression = bool(user_row[7])

    if recipient_email == "":
        return "skip_missing_email", None
    if primary_email_confirmed is not True:
        return "skip_unconfirmed_email", None
    if account_status != "confirmed":
        return "skip_other", None
    if has_newsletter_suppression is True:
        return "skip_suppressed", "suppressed:newsletters"
    if email_communication_preference not in {"newsletters", "all_email"}:
        return "skip_preference", None
    if preferred_language_id is None:
        if english_variant is None:
            return "skip_other", "missing_translation:en"
        return "send", None
    if preferred_language_id != resolved_variant[1]:
        return "skip_other", f"missing_translation:{user_row[3]}"
    return "send", None
