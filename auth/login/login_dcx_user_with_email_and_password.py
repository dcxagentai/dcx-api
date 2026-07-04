"""
CONTEXT:
This file authenticates one DCX user by email and password and issues a new session.
It exists so both the app and admin frontends can share one login capability while the normalized
contact-method layer owns which verified email addresses may authenticate for each user.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from auth.authorization.read_dcx_user_role_may_access_admin import (
    read_dcx_user_role_may_access_admin,
)
from auth.password.verify_dcx_password_hash import verify_dcx_password_hash
from auth.session.create_dcx_auth_session import create_dcx_auth_session
from storage.db_config import DB_CONFIG


def login_dcx_user_with_email_and_password(
    email: str,
    candidate_password: str,
    request_ip: str | None,
    request_user_agent: str | None,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email is the submitted login email.
        - candidate_password is the submitted plaintext password.
        - The configured database is reachable.
      postconditions:
        - Returns one authenticated session payload when the email/password pair is valid.
        - Creates one durable session row for the user.
      side_effects:
        - may write one new auth session row
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: login creates append-only session rows, so no explicit lock is required

    NARRATIVE:
      WHY this exists:
        - The MVP needs one canonical login capability shared by app and admin.
      WHEN TO USE it:
        - Use it from the email/password login route.
      WHEN NOT TO USE it:
        - Do not use it for password setup or reset completion.
      WHAT CAN GO WRONG:
        - The email may not belong to one verified login-enabled email contact method.
        - The user may not exist.
        - The user may not have set a password yet.
        - The password may be wrong.
        - The database may be unavailable.
      WHAT COMES NEXT:
        - The route sets the returned raw session token into the shared browser cookie.

    TESTS:
      - login_returns_session_payload_for_valid_email_and_password
      - login_raises_invalid_credentials_for_wrong_password
      - login_raises_invalid_credentials_when_password_not_set

    ERRORS:
      - API_DCX_AUTH_LOGIN_INVALID_CREDENTIALS:
          suggested_action: Retry with the correct email and password, or use the password setup/reset flow.
          common_causes:
            - wrong password
            - no password set yet
            - unknown email
            - account not confirmed
          recovery_steps:
            - Re-enter the credentials carefully.
            - Use password setup or reset if needed.
          retry_safe: true
      - API_DCX_AUTH_LOGIN_READ_FAILED:
          suggested_action: Confirm backend/database health and retry login after the service is stable.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true

    CODE:
    """
    normalized_email = email.strip().lower()
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        u.id,
                        u.user_uuid,
                        cm.normalized_value,
                        u.user_role,
                        u.account_status,
                        cm.is_verified,
                        pc.password_hash
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
                    LEFT JOIN stephen_dcx_user_password_credentials pc
                      ON pc.user_id = u.id
                    WHERE cm.contact_type = %s
                      AND cm.normalized_value = %s
                      AND cm.is_active = TRUE
                      AND cm.is_login_enabled = TRUE
                    LIMIT 1
                    """,
                    (
                        "email",
                        normalized_email,
                        "email",
                        normalized_email,
                    ),
                )
                user_row = cursor.fetchone()
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_AUTH_LOGIN_READ_FAILED") from exc

    if (
        user_row is None
        or user_row[6] in {None, ""}
        or user_row[5] is not True
        or user_row[4] != "confirmed"
        or not verify_dcx_password_hash(candidate_password, user_row[6])
    ):
        raise RuntimeError("API_DCX_AUTH_LOGIN_INVALID_CREDENTIALS")

    session_payload = create_dcx_auth_session(
        authenticated_user_id=user_row[0],
        created_from_ip=request_ip,
        created_from_user_agent=request_user_agent,
        connect_to_database=connect,
    )

    user_role = user_row[3]

    return {
        "session_id": session_payload["session_id"],
        "raw_session_token": session_payload["raw_session_token"],
        "session_expires_at_ts_ms": session_payload["expires_at_ts_ms"],
        "user": {
            "user_id": user_row[0],
            "user_uuid": str(user_row[1]),
            "primary_email": user_row[2],
            "user_role": user_role,
            "account_status": user_row[4],
            "allowed_surfaces": {
                "app": True,
                "admin": read_dcx_user_role_may_access_admin(user_role),
            },
        },
    }
