"""
CONTEXT:
This file reads one confirmed DCX email identity suitable for password setup or reset.
It exists so signup-completion and forgotten-password flows can share the same normalized
contact-method plus auth-identity lookup rules without duplicating the confirmed-email checks
across multiple capabilities.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_confirmed_dcx_user_identity_for_password_link_by_email(
    normalized_email: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - normalized_email is one lowercased canonical email string.
      postconditions:
        - Returns the confirmed user/identity payload when the email belongs to a confirmed DCX user with one verified login-enabled email contact method and matching email identity.
        - Returns null when no eligible identity exists.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Password links should only target confirmed users tied to one verified login-enabled email contact method and matching email identity.
      WHEN TO USE it:
        - Use it before creating password setup or reset challenges for one email address.
      WHEN NOT TO USE it:
        - Do not use it for ordinary login lookups or session reads.
      WHAT CAN GO WRONG:
        - Unknown or unconfirmed users should simply return no eligible payload.
        - The database can be unavailable.
      WHAT COMES NEXT:
        - The caller can create or refresh a password-link challenge for the returned identity.

    TESTS:
      - returns_confirmed_user_identity_payload_for_verified_login_enabled_email_contact_method
      - returns_none_for_unconfirmed_user

    ERRORS:
      - API_DCX_PASSWORD_LINK_USER_READ_FAILED:
          suggested_action: Confirm database health and retry once the backend is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry the request.
          retry_safe: true

    CODE:
    """
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        u.id,
                        cm.normalized_value,
                        i.id,
                        l.language_code
                    FROM stephen_dcx_users_contact_methods cm
                    JOIN stephen_dcx_users u
                      ON u.id = cm.user_id
                    JOIN stephen_dcx_user_auth_identities i
                      ON i.user_id = u.id
                     AND i.contact_method_id = cm.id
                     AND i.provider_type = %s
                     AND LOWER(i.provider_subject) = %s
                     AND i.provider_email_confirmed = TRUE
                     AND i.is_login_enabled = TRUE
                    LEFT JOIN stephen_dcx_languages l
                      ON l.id = u.preferred_language_id
                    WHERE cm.contact_type = %s
                      AND cm.normalized_value = %s
                      AND cm.is_active = TRUE
                      AND cm.is_verified = TRUE
                      AND cm.is_login_enabled = TRUE
                      AND u.account_status = %s
                    LIMIT 1
                    """,
                    (
                        "email",
                        normalized_email,
                        "email",
                        normalized_email,
                        "confirmed",
                    ),
                )
                row = cursor.fetchone()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_PASSWORD_LINK_USER_READ_FAILED") from exc

    if row is None:
        return None

    return {
        "user_id": row[0],
        "delivery_email": row[1],
        "user_auth_identity_id": row[2],
        "language_code": row[3] or "en",
    }
