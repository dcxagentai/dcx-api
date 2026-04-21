"""
CONTEXT:
This file saves one DCX email sequence and its full ordered step list.
It exists so the admin sequence editor can update one coherent planning object in a single
transaction rather than trying to orchestrate multiple partial step mutations from the frontend.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from content.shared.build_dcx_slugified_text_identifier import (
    build_dcx_slugified_text_identifier,
)
from storage.db_config import DB_CONFIG


def save_dcx_admin_email_sequence_and_steps_capability(
    authenticated_admin_user_id: int,
    sequence_key: str,
    sequence_name: str,
    sequence_type: str,
    audience_type: str,
    trigger_type: str,
    scheduled_launch_at_ts_ms: int | None,
    is_live: bool,
    steps: list[dict],
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_admin_user_id identifies one current admin/dev user.
        - sequence_key identifies one existing sequence row.
        - sequence_name is one non-empty human-readable name.
        - sequence_type is one of `campaign` or `onboarding`.
        - audience_type is one of `newsletters` or `all_email`.
        - trigger_type is one of `user_signup`, `manual_launch`, or `scheduled_launch`.
        - steps is one ordered list of step objects that reference valid live original sequence-email ids.
        - The configured database is reachable.
      postconditions:
        - Updates the requested sequence metadata.
        - Replaces the existing step set with the submitted ordered step set.
        - Enforces the scheduled-launch timestamp contract declared by the table schema.
      side_effects:
        - updates one sequence row
        - deletes prior sequence steps
        - inserts replacement sequence steps
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - transaction-scoped advisory lock on the target sequence key
      contention_strategy: serialize competing saves for the same sequence

    NARRATIVE:
      WHY this exists:
        - The first sequence editor should save one coherent snapshot instead of requiring brittle step-by-step writes.
      WHEN TO USE it:
        - Use it from the admin sequence detail screen.
      WHEN NOT TO USE it:
        - Do not use it to dispatch sequence sends.
      WHAT CAN GO WRONG:
        - The sequence can be missing.
        - The submitted metadata can violate the sequence schema contract.
        - A step can reference one missing or disallowed email row.
      WHAT COMES NEXT:
        - The detail route can be reloaded to show the normalized saved state.

    TESTS:
      - updates_sequence_metadata_and_replaces_steps
      - raises_clear_error_when_sequence_missing
      - raises_clear_error_for_invalid_sequence_payload

    ERRORS:
      - API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID:
          suggested_action: Correct the sequence fields and retry the save.
          common_causes:
            - blank sequence name
            - invalid enum value
            - missing scheduled launch timestamp for scheduled_launch
            - invalid step source email id
            - step source email is not one live original sequence email
          recovery_steps:
            - Review the form fields.
            - Retry with valid sequence metadata and steps.
          retry_safe: true
          what_changed: nothing was written
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_NOT_FOUND:
          suggested_action: Refresh the sequences list and reopen the current row before saving again.
          common_causes:
            - stale sequence route
            - deleted sequence
          recovery_steps:
            - Reload the sequence catalog.
            - Reopen the target sequence.
          retry_safe: true
          what_changed: nothing was written
          rollback_needed: false
          rollback_operation: none
      - API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_FAILED:
          suggested_action: Retry once the backend and database are healthy.
          common_causes:
            - database unavailable
            - foreign-key failure
            - insert/update failure
          recovery_steps:
            - Verify database connectivity.
            - Retry after the backend is healthy.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the target sequence row before retrying

    CODE:
    """
    normalized_sequence_key = sequence_key.strip()
    normalized_sequence_name = sequence_name.strip()
    normalized_sequence_type = sequence_type.strip().lower()
    normalized_audience_type = audience_type.strip().lower()
    normalized_trigger_type = trigger_type.strip().lower()
    normalized_is_live = bool(is_live)
    normalized_steps = steps if isinstance(steps, list) else []

    if (
        authenticated_admin_user_id <= 0
        or normalized_sequence_key == ""
        or normalized_sequence_name == ""
        or normalized_sequence_type not in {"campaign", "onboarding"}
        or normalized_audience_type not in {"newsletters", "all_email"}
        or normalized_trigger_type not in {"user_signup", "manual_launch", "scheduled_launch"}
    ):
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID")

    normalized_scheduled_launch_at_ts_ms = (
        scheduled_launch_at_ts_ms
        if isinstance(scheduled_launch_at_ts_ms, int) and scheduled_launch_at_ts_ms > 0
        else None
    )
    if normalized_trigger_type == "scheduled_launch" and normalized_scheduled_launch_at_ts_ms is None:
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID")
    if normalized_trigger_type != "scheduled_launch" and normalized_scheduled_launch_at_ts_ms is not None:
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID")

    normalized_step_rows = _read_normalized_sequence_step_rows_or_error(normalized_steps)
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"dcx_email_sequence_save:{normalized_sequence_key}",),
                )
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_emails_sequences
                    WHERE sequence_key = %s
                    LIMIT 1
                    """,
                    (normalized_sequence_key,),
                )
                sequence_row = cursor.fetchone()
                if sequence_row is None:
                    raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_NOT_FOUND")

                sequence_id = sequence_row[0]
                _assert_sequence_step_source_email_ids_are_valid_or_error(
                    cursor=cursor,
                    step_rows=normalized_step_rows,
                )
                cursor.execute(
                    """
                    UPDATE stephen_dcx_emails_sequences
                    SET sequence_name = %s,
                        sequence_type = %s,
                        audience_type = %s,
                        trigger_type = %s,
                        scheduled_launch_at_ts_ms = %s,
                        is_live = %s,
                        updated_by_user_id = %s
                    WHERE id = %s
                    """,
                    (
                        normalized_sequence_name,
                        normalized_sequence_type,
                        normalized_audience_type,
                        normalized_trigger_type,
                        normalized_scheduled_launch_at_ts_ms,
                        normalized_is_live,
                        authenticated_admin_user_id,
                        sequence_id,
                    ),
                )

                cursor.execute(
                    "DELETE FROM stephen_dcx_emails_sequence_steps WHERE sequence_id = %s",
                    (sequence_id,),
                )

                for step_index, step_row in enumerate(normalized_step_rows, start=1):
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_emails_sequence_steps (
                            sequence_id,
                            step_key,
                            step_name,
                            step_order,
                            source_email_id,
                            delay_minutes_from_trigger,
                            is_active
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            sequence_id,
                            step_row["step_key"],
                            step_row["step_name"],
                            step_index,
                            step_row["source_email_id"],
                            step_row["delay_minutes_from_trigger"],
                            step_row["is_active"],
                        ),
                    )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_FAILED") from exc

    return {
        "sequence_id": sequence_id,
        "sequence_key": normalized_sequence_key,
        "saved_step_count": len(normalized_step_rows),
    }


def _read_normalized_sequence_step_rows_or_error(steps: list[dict]) -> list[dict]:
    normalized_rows: list[dict] = []
    used_step_keys: set[str] = set()

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID")

        step_name = str(step.get("step_name", "")).strip()
        source_email_id = step.get("source_email_id")
        delay_minutes_from_trigger = step.get("delay_minutes_from_trigger")
        is_active = bool(step.get("is_active", True))
        candidate_step_key = str(step.get("step_key", "")).strip()

        if step_name == "":
            step_name = f"Step {index}"
        if not isinstance(source_email_id, int) or source_email_id <= 0:
            raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID")
        if not isinstance(delay_minutes_from_trigger, int) or delay_minutes_from_trigger < 0:
            raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID")

        base_step_key = (
            build_dcx_slugified_text_identifier(candidate_step_key)
            if candidate_step_key != ""
            else build_dcx_slugified_text_identifier(step_name)
        )
        if base_step_key == "":
            base_step_key = f"step-{index}"

        next_step_key = base_step_key
        suffix_counter = 2
        while next_step_key in used_step_keys:
            next_step_key = f"{base_step_key}-{suffix_counter}"
            suffix_counter += 1
        used_step_keys.add(next_step_key)

        normalized_rows.append(
            {
                "step_key": next_step_key,
                "step_name": step_name,
                "source_email_id": source_email_id,
                "delay_minutes_from_trigger": delay_minutes_from_trigger,
                "is_active": is_active,
            }
        )

    return normalized_rows


def _assert_sequence_step_source_email_ids_are_valid_or_error(
    cursor: Any,
    step_rows: list[dict],
) -> None:
    unique_source_email_ids = sorted(
        {
            int(step_row["source_email_id"])
            for step_row in step_rows
        }
    )
    if not unique_source_email_ids:
        return

    cursor.execute(
        """
        SELECT id
        FROM stephen_dcx_emails
        WHERE id = ANY(%s)
          AND email_type = 'sequence'
          AND is_original = TRUE
          AND is_live = TRUE
        """,
        (unique_source_email_ids,),
    )
    valid_source_rows = cursor.fetchall()
    valid_source_email_ids = {valid_row[0] for valid_row in valid_source_rows}

    if len(valid_source_email_ids) != len(unique_source_email_ids):
        raise RuntimeError("API_DCX_ADMIN_EMAIL_SEQUENCE_SAVE_INVALID")
