"""
CONTEXT:
This file resets the active DCX public email-signup challenge cooldown after a provider send failure.
It exists so signup and resend routes can recover from delivery errors without leaving the user stranded
behind a cooldown window for an email that never actually arrived.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def reset_public_email_signup_send_cooldown_after_delivery_failure_capability(
    challenge_id: int,
    recovery_action: str,
    prior_delivery_target: str | None = None,
    prior_otp_hash: str | None = None,
    prior_otp_salt: str | None = None,
    prior_expires_at_ts_ms: int | None = None,
    prior_sent_at_ts_ms: int | None = None,
    prior_last_attempted_at_ts_ms: int | None = None,
    prior_attempt_count: int | None = None,
    prior_max_attempt_count: int | None = None,
    prior_resend_count: int | None = None,
    prior_send_count: int | None = None,
    prior_next_send_allowed_at_ts_ms: int | None = None,
    prior_locked_until_ts_ms: int | None = None,
    prior_public_signup_flow_token_hash: str | None = None,
    prior_public_signup_flow_token_expires_at_ts_ms: int | None = None,
    prior_send_budget_window_started_at_ts_ms: int | None = None,
    prior_send_budget_request_count: int | None = None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - challenge_id identifies the active public email-signup challenge whose delivery attempt failed.
        - recovery_action is either delete_new_challenge or restore_existing_challenge_state.
        - prior_* values came from the same challenge row immediately before the attempted send mutation when restoration is needed.
        - The configured database is reachable.
      postconditions:
        - Deletes a newly created unsent challenge or restores the prior mutable challenge state exactly.
        - Leaves the flow recoverable after the provider failure.
      side_effects:
        - writes to stephen_dcx_user_auth_challenges
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: public_email_signup_delivery_failure_recovery:{challenge_id}
      locks:
        - row lock on the targeted challenge row
      contention_strategy: serialize recovery on the challenge row and keep the mutation minimal

    NARRATIVE:
      WHY this exists:
        - A provider send failure should not trap the user behind a cooldown for an OTP email that never arrived.
      WHEN TO USE it:
        - Use it when the Resend send capability raises after a challenge row was already created or refreshed.
      WHEN NOT TO USE it:
        - Do not use it after a confirmed successful email send.
      WHAT CAN GO WRONG:
        - Database connectivity issues can prevent the recovery mutation.
      WHAT COMES NEXT:
        - The user can retry signup or resend immediately.

    TESTS:
      - deletes_new_unsent_challenge_after_failed_delivery
      - restores_existing_challenge_state_after_failed_delivery

    ERRORS:
      - API_PUBLIC_EMAIL_SIGNUP_DELIVERY_FAILURE_RECOVERY_FAILED:
          suggested_action: Confirm database health and retry the public signup flow.
          common_causes:
            - database unavailable
            - transaction failure
          recovery_steps:
            - Verify database connectivity.
            - Retry the signup or resend request.
          retry_safe: true
          what_changed: unknown until the transaction outcome is inspected
          rollback_needed: false
          rollback_operation: rely on transaction rollback if the update failed

    CODE:
    """
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = (current_timestamp_ms_provider or _current_timestamp_ms_provider)()

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM stephen_dcx_user_auth_challenges WHERE id = %s FOR UPDATE",
                    (challenge_id,),
                )

                if recovery_action == "delete_new_challenge":
                    cursor.execute(
                        "DELETE FROM stephen_dcx_user_auth_challenges WHERE id = %s",
                        (challenge_id,),
                    )
                elif recovery_action == "restore_existing_challenge_state":
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_user_auth_challenges
                        SET
                            delivery_target = %s,
                            otp_hash = %s,
                            otp_salt = %s,
                            expires_at_ts_ms = %s,
                            sent_at_ts_ms = %s,
                            last_attempted_at_ts_ms = %s,
                            attempt_count = %s,
                            max_attempt_count = %s,
                            resend_count = %s,
                            send_count = %s,
                            next_send_allowed_at_ts_ms = %s,
                            locked_until_ts_ms = %s,
                            public_signup_flow_token_hash = %s,
                            public_signup_flow_token_expires_at_ts_ms = %s,
                            send_budget_window_started_at_ts_ms = %s,
                            send_budget_request_count = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            prior_delivery_target,
                            prior_otp_hash,
                            prior_otp_salt,
                            prior_expires_at_ts_ms,
                            prior_sent_at_ts_ms,
                            prior_last_attempted_at_ts_ms,
                            prior_attempt_count,
                            prior_max_attempt_count,
                            prior_resend_count,
                            prior_send_count,
                            prior_next_send_allowed_at_ts_ms,
                            prior_locked_until_ts_ms,
                            prior_public_signup_flow_token_hash,
                            prior_public_signup_flow_token_expires_at_ts_ms,
                            prior_send_budget_window_started_at_ts_ms,
                            prior_send_budget_request_count,
                            now_ts_ms,
                            challenge_id,
                        ),
                    )
                else:
                    raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_DELIVERY_FAILURE_RECOVERY_FAILED")
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_PUBLIC_EMAIL_SIGNUP_DELIVERY_FAILURE_RECOVERY_FAILED") from exc

    return {
        "challenge_id": challenge_id,
        "recovery_action": recovery_action,
    }


def _current_timestamp_ms_provider() -> int:
    """Minimal contract: return the current unix timestamp in milliseconds."""
    return int(__import__("time").time() * 1000)
