"""
CONTEXT:
This file sets one verified phone contact method as the authenticated DCX user's primary phone.
It exists so primary-phone selection is an explicit user action instead of an automatic side effect
of verifying a newly added phone number.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def set_authenticated_dcx_user_primary_phone_contact_method(
    authenticated_user_id: int,
    phone_contact_method_id: int,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id identifies one authenticated DCX user.
        - phone_contact_method_id identifies one active phone contact method that belongs to that user.
        - The target phone contact method is already verified.
        - The configured database is reachable.
      postconditions:
        - The requested verified phone contact method becomes the user's primary phone contact method.
        - Other active primary phone contact methods for the user are demoted.
      side_effects:
        - updates stephen_dcx_users_contact_methods
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: dcx_primary_phone_contact_method:{authenticated_user_id}:{phone_contact_method_id}
      locks:
        - row lock on the owning user row
        - row lock on the requested phone contact method row
        - row lock on the user's other primary phone contact method rows
      contention_strategy: serialize primary-phone selection for one user, then demote and promote rows inside one transaction

    NARRATIVE:
      WHY this exists:
        - Primary contact identity should only change through an explicit user choice.
      WHEN TO USE it:
        - Use it when an authenticated user chooses one already-verified phone as their primary account phone.
      WHEN NOT TO USE it:
        - Do not use it to verify phones.
        - Do not use it for unverified phone contact methods.
      WHAT CAN GO WRONG:
        - The target phone may not belong to the user.
        - The target phone may still be unverified.
        - Database writes can fail.
      WHAT COMES NEXT:
        - The account-summary read path will reflect the new primary phone immediately.

    TESTS:
      - verified_phone_becomes_primary_and_existing_primary_is_demoted
      - unverified_phone_cannot_become_primary

    ERRORS:
      - API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND:
          suggested_action: Sign in again and retry after confirming the user account still exists.
          common_causes:
            - stale session principal
            - deleted user row
          recovery_steps:
            - Sign in again.
            - Inspect the user row if needed.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_FOUND:
          suggested_action: Refresh the account page and retry from one phone number that belongs to this account.
          common_causes:
            - stale contact-method id
            - phone row belongs to another user
          recovery_steps:
            - Refresh the account page.
            - Retry with one current phone row from this account.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_VERIFIED:
          suggested_action: Verify the phone number first, then retry setting it as primary.
          common_causes:
            - unverified phone row
            - verification not completed yet
          recovery_steps:
            - Finish phone verification.
            - Retry once the phone shows as verified.
          retry_safe: true
      - API_AUTHENTICATED_DCX_USER_PRIMARY_PHONE_SET_FAILED:
          suggested_action: Confirm database health and retry after the backend is stable.
          common_causes:
            - database unavailable
            - transaction failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true

    CODE:
    """
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND")

    if not isinstance(phone_contact_method_id, int) or phone_contact_method_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_users
                    WHERE id = %s
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (authenticated_user_id,),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT
                        id,
                        is_primary,
                        is_verified
                    FROM stephen_dcx_users_contact_methods
                    WHERE id = %s
                      AND user_id = %s
                      AND contact_type = %s
                      AND is_active = TRUE
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (
                        phone_contact_method_id,
                        authenticated_user_id,
                        "phone",
                    ),
                )
                target_phone_contact_method_row = cursor.fetchone()
                if target_phone_contact_method_row is None:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_FOUND")

                if target_phone_contact_method_row[2] is not True:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_PHONE_CONTACT_METHOD_NOT_VERIFIED")

                if target_phone_contact_method_row[1] is True:
                    return {
                        "status": "already_primary",
                        "phone_contact_method_id": phone_contact_method_id,
                    }

                cursor.execute(
                    """
                    UPDATE stephen_dcx_users_contact_methods
                    SET
                        is_primary = FALSE,
                        display_label = CASE
                            WHEN display_label = %s THEN %s
                            ELSE display_label
                        END,
                        updated_at_ts_ms = %s
                    WHERE user_id = %s
                      AND contact_type = %s
                      AND is_primary = TRUE
                      AND is_active = TRUE
                      AND id <> %s
                    """,
                    (
                        "primary",
                        "",
                        now_ts_ms,
                        authenticated_user_id,
                        "phone",
                        phone_contact_method_id,
                    ),
                )

                cursor.execute(
                    """
                    UPDATE stephen_dcx_users_contact_methods
                    SET
                        is_primary = TRUE,
                        display_label = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (
                        "primary",
                        now_ts_ms,
                        phone_contact_method_id,
                    ),
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_PRIMARY_PHONE_SET_FAILED") from exc

    return {
        "status": "primary_updated",
        "phone_contact_method_id": phone_contact_method_id,
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
