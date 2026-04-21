"""
CONTEXT:
This file applies one public DCX email unsubscribe request from a signed email link.
It exists so email recipients can change newsletter or promotional email behavior without already
being signed into the app.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG
from users.account.dcx_email_preference_unsubscribe_support import (
    DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_ALL,
    DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_NEWSLETTERS,
    DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_PROMOTIONAL,
    read_dcx_email_preference_unsubscribe_token_payload,
)


def apply_dcx_public_email_unsubscribe_request_capability(
    unsubscribe_kind: str,
    raw_unsubscribe_token: str,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - unsubscribe_kind is one supported DCX unsubscribe kind.
        - raw_unsubscribe_token is one valid signed unsubscribe token from a DCX email.
        - The configured database is reachable.
      postconditions:
        - Applies the requested unsubscribe behavior for the resolved user and primary email contact.
        - Returns one summary describing the resulting preference and newsletter suppression state.
      side_effects:
        - updates one `stephen_dcx_users` row when needed
        - may insert or update one `stephen_dcx_emails_suppressions` row for newsletter-only unsubscribes
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: public_email_unsubscribe:{unsubscribe_kind}:{raw_unsubscribe_token}
      locks:
        - one row-level lock on the target `stephen_dcx_users.id`
      contention_strategy: serialize concurrent unsubscribe requests for the same user so preference and suppression writes remain coherent

    NARRATIVE:
      WHY this exists:
        - Recipients need one-click unsubscribe behavior from email itself, not only from a signed-in account page.
      WHEN TO USE it:
        - Use it from the public email unsubscribe route only.
      WHEN NOT TO USE it:
        - Do not use it for authenticated account settings saves.
        - Do not use it for provider-driven bounces or complaints.
      WHAT CAN GO WRONG:
        - The token can be invalid, expired, or tied to a stale primary email.
        - The user row can be missing.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The route can show a human-readable confirmation page, and later webhook logic can keep provider suppressions aligned.

    TESTS:
      - unsubscribe_all_sets_user_preference_to_no_email
      - unsubscribe_promotional_steps_down_to_newsletters
      - unsubscribe_newsletters_from_all_email_creates_newsletter_suppression

    ERRORS:
      - API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_INVALID:
          suggested_action: Retry from the full unsubscribe link in the newest email.
          common_causes:
            - invalid kind
            - token kind mismatch
            - stale primary email does not match the token payload
          recovery_steps:
            - Reopen the original email.
            - Retry from the full unsubscribe URL.
          retry_safe: true
          what_changed: nothing was written
          rollback_needed: false
          rollback_operation: none
      - API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_EXPIRED:
          suggested_action: Use a newer email or update email preferences from the signed-in account page.
          common_causes:
            - old unsubscribe link
          recovery_steps:
            - Reopen the most recent email.
            - Or sign in and update account settings directly.
          retry_safe: true
          what_changed: nothing was written
          rollback_needed: false
          rollback_operation: none
      - API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_NOT_FOUND:
          suggested_action: Retry from a newer email or update preferences from the signed-in account page.
          common_causes:
            - user deleted
            - user no longer has the same primary email contact
          recovery_steps:
            - Reopen the newest email.
            - Or update the account from inside the app.
          retry_safe: true
          what_changed: nothing was written
          rollback_needed: false
          rollback_operation: none
      - API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - write failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the target user and suppression rows before manual replay

    CODE:
    """
    try:
        token_payload = read_dcx_email_preference_unsubscribe_token_payload(
            raw_unsubscribe_token,
            current_timestamp_ms_provider=current_timestamp_ms_provider,
        )
    except RuntimeError as exc:
        if str(exc) == "API_DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_TOKEN_EXPIRED":
            raise RuntimeError("API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_EXPIRED") from exc
        raise RuntimeError("API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_INVALID") from exc

    normalized_unsubscribe_kind = token_payload["unsubscribe_kind"]
    if normalized_unsubscribe_kind != unsubscribe_kind.strip().lower():
        raise RuntimeError("API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_INVALID")

    current_timestamp_ms = (
        current_timestamp_ms_provider() if current_timestamp_ms_provider else _read_current_timestamp_ms()
    )
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        user_row.id,
                        user_row.email_communication_preference,
                        primary_email_contact_method.id,
                        primary_email_contact_method.normalized_value
                    FROM stephen_dcx_users AS user_row
                    LEFT JOIN LATERAL (
                        SELECT
                            id,
                            normalized_value
                        FROM stephen_dcx_users_contact_methods
                        WHERE user_id = user_row.id
                          AND contact_type = 'email'
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) AS primary_email_contact_method
                      ON TRUE
                    WHERE user_row.id = %s
                    FOR UPDATE
                    """,
                    (token_payload["user_id"],),
                )
                user_row = cursor.fetchone()
                if user_row is None:
                    raise RuntimeError("API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_NOT_FOUND")

                primary_contact_method_id = user_row[2]
                primary_recipient_email = (user_row[3] or "").strip().lower()
                if (
                    primary_contact_method_id is None
                    or primary_recipient_email == ""
                    or primary_recipient_email != token_payload["recipient_email"]
                ):
                    raise RuntimeError("API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_NOT_FOUND")

                current_preference = (user_row[1] or "").strip().lower()
                next_preference = current_preference
                newsletter_suppression_active = False

                if normalized_unsubscribe_kind == DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_ALL:
                    next_preference = "no_email"
                elif normalized_unsubscribe_kind == DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_PROMOTIONAL:
                    if current_preference == "all_email":
                        next_preference = "newsletters"
                elif normalized_unsubscribe_kind == DCX_EMAIL_PREFERENCE_UNSUBSCRIBE_NEWSLETTERS:
                    if current_preference == "newsletters":
                        next_preference = "no_email"
                    elif current_preference == "all_email":
                        next_preference = "all_email"
                        _ensure_active_newsletters_unsubscribe_suppression(
                            cursor=cursor,
                            user_id=user_row[0],
                            contact_method_id=primary_contact_method_id,
                            normalized_contact_value=primary_recipient_email,
                            current_timestamp_ms=current_timestamp_ms,
                        )
                        newsletter_suppression_active = True

                cursor.execute(
                    """
                    UPDATE stephen_dcx_users
                    SET email_communication_preference = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    RETURNING email_communication_preference
                    """,
                    (
                        next_preference,
                        current_timestamp_ms,
                        user_row[0],
                    ),
                )
                saved_preference_row = cursor.fetchone()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_PUBLIC_EMAIL_UNSUBSCRIBE_FAILED") from exc

    return {
        "user_id": token_payload["user_id"],
        "recipient_email": token_payload["recipient_email"],
        "unsubscribe_kind": normalized_unsubscribe_kind,
        "email_communication_preference": saved_preference_row[0],
        "newsletters_suppressed": newsletter_suppression_active,
    }


def _ensure_active_newsletters_unsubscribe_suppression(
    cursor: Any,
    user_id: int,
    contact_method_id: int,
    normalized_contact_value: str,
    current_timestamp_ms: int,
) -> None:
    cursor.execute(
        """
        SELECT id
        FROM stephen_dcx_emails_suppressions
        WHERE is_active = TRUE
          AND normalized_contact_value = %s
          AND suppression_scope = 'newsletters'
        LIMIT 1
        """,
        (normalized_contact_value,),
    )
    active_suppression_row = cursor.fetchone()
    if active_suppression_row is not None:
        cursor.execute(
            """
            UPDATE stephen_dcx_emails_suppressions
            SET user_id = %s,
                contact_method_id = %s,
                suppression_source = 'unsubscribe',
                suppression_reason = 'user_unsubscribe:newsletters',
                provider_name = 'dcx',
                provider_reference_id = 'unsubscribe:newsletters',
                updated_at_ts_ms = %s
            WHERE id = %s
            """,
            (
                user_id,
                contact_method_id,
                current_timestamp_ms,
                active_suppression_row[0],
            ),
        )
        return

    cursor.execute(
        """
        INSERT INTO stephen_dcx_emails_suppressions (
            user_id,
            contact_method_id,
            normalized_contact_value,
            suppression_source,
            suppression_scope,
            suppression_reason,
            provider_name,
            provider_reference_id,
            suppressed_at_ts_ms,
            is_active
        )
        VALUES (%s, %s, %s, 'unsubscribe', 'newsletters', 'user_unsubscribe:newsletters', 'dcx', 'unsubscribe:newsletters', %s, TRUE)
        """,
        (
            user_id,
            contact_method_id,
            normalized_contact_value,
            current_timestamp_ms,
        ),
    )


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)
