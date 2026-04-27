"""
CONTEXT:
This file stores one inbound or outbound provider event row for the DCX contact-message domain.
It exists so webhook and provider-originated traffic has one canonical audit and deduplication layer
before it becomes one or more DCX contact-message rows.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

import psycopg2
import psycopg2.extras

from storage.db_config import DB_CONFIG


def store_dcx_contact_message_provider_event(
    provider_type: str,
    channel_type: str,
    provider_event_type: str,
    raw_event_payload_json: dict,
    provider_event_id: str | None = None,
    provider_message_id: str | None = None,
    provider_sender_handle: str | None = None,
    provider_recipient_handle: str | None = None,
    user_id: int | None = None,
    contact_method_id: int | None = None,
    signature_verified: bool = False,
    processing_status: str = "processed",
    event_received_at_ts_ms: int | None = None,
    connect_to_database: Callable[..., Any] | None = None,
    current_timestamp_ms_provider: Callable[[], int] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - provider_type and channel_type are supported canonical values for the contact-message domain.
        - raw_event_payload_json is the parsed provider payload that triggered this storage step.
        - The configured database is reachable.
      postconditions:
        - Persists one provider-event row or reuses the existing row for the same provider event id.
        - Returns the stored provider-event id plus the payload hash.
      side_effects:
        - writes to stephen_dcx_contact_message_provider_events
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: provider_event:{provider_type}:{provider_event_id}
      locks:
        - unique index contention on provider_type + provider_event_id when a provider event id is present
      contention_strategy: duplicate webhook deliveries converge on the same provider-event row through upsert behavior

    NARRATIVE:
      WHY this exists:
        - The new omnichannel message system needs one durable place to keep raw provider events before
          they become user-visible normalized messages.
      WHEN TO USE it:
        - Use it from inbound webhook handlers after signature verification succeeds.
      WHEN NOT TO USE it:
        - Do not use it for browser-authenticated app message creation.
      WHAT CAN GO WRONG:
        - The payload can be malformed for JSON serialization.
        - The database can be unavailable.
      WHAT COMES NEXT:
        - Stored provider events can later support replay, debugging, and richer webhook convergence logic.

    TESTS:
      - none yet in this first webhook-ingest pass

    ERRORS:
      - API_DCX_CONTACT_MESSAGE_PROVIDER_EVENT_STORE_FAILED:
          suggested_action: Retry after the backend and database are healthy.
          common_causes:
            - database unavailable
            - invalid payload serialization
          recovery_steps:
            - Confirm database connectivity.
            - Confirm the provider payload is valid JSON.
            - Retry once the backend is stable.
          retry_safe: true
          what_changed: unknown if the transaction boundary is not trusted
          rollback_needed: inspect_if_partial_commit_suspected
          rollback_operation: inspect the provider-events table before manual replay

    CODE:
    """
    normalized_provider_event_id = (
        provider_event_id.strip() if isinstance(provider_event_id, str) else None
    ) or None
    normalized_provider_message_id = (
        provider_message_id.strip() if isinstance(provider_message_id, str) else None
    ) or None
    now_ts_ms = (current_timestamp_ms_provider or _read_current_timestamp_ms)()
    received_ts_ms = event_received_at_ts_ms or now_ts_ms
    payload_hash = hashlib.sha256(
        json.dumps(raw_event_payload_json, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                if normalized_provider_event_id is not None:
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_contact_message_provider_events (
                            user_id,
                            contact_method_id,
                            provider_type,
                            channel_type,
                            provider_event_type,
                            provider_event_id,
                            provider_message_id,
                            provider_sender_handle,
                            provider_recipient_handle,
                            event_direction,
                            payload_hash,
                            raw_event_payload_json,
                            signature_verified,
                            processing_status,
                            event_received_at_ts_ms,
                            event_processed_at_ts_ms
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'inbound', %s, %s::jsonb, %s, %s, %s, %s)
                        ON CONFLICT (provider_type, provider_event_id)
                        WHERE provider_event_id IS NOT NULL
                        DO UPDATE
                        SET
                            user_id = COALESCE(stephen_dcx_contact_message_provider_events.user_id, EXCLUDED.user_id),
                            contact_method_id = COALESCE(stephen_dcx_contact_message_provider_events.contact_method_id, EXCLUDED.contact_method_id),
                            provider_message_id = COALESCE(stephen_dcx_contact_message_provider_events.provider_message_id, EXCLUDED.provider_message_id),
                            provider_sender_handle = COALESCE(stephen_dcx_contact_message_provider_events.provider_sender_handle, EXCLUDED.provider_sender_handle),
                            provider_recipient_handle = COALESCE(stephen_dcx_contact_message_provider_events.provider_recipient_handle, EXCLUDED.provider_recipient_handle),
                            payload_hash = EXCLUDED.payload_hash,
                            raw_event_payload_json = EXCLUDED.raw_event_payload_json,
                            signature_verified = stephen_dcx_contact_message_provider_events.signature_verified OR EXCLUDED.signature_verified,
                            processing_status = EXCLUDED.processing_status,
                            event_processed_at_ts_ms = EXCLUDED.event_processed_at_ts_ms,
                            updated_at_ts_ms = %s
                        RETURNING id
                        """,
                        (
                            user_id,
                            contact_method_id,
                            provider_type,
                            channel_type,
                            provider_event_type,
                            normalized_provider_event_id,
                            normalized_provider_message_id,
                            provider_sender_handle,
                            provider_recipient_handle,
                            payload_hash,
                            psycopg2.extras.Json(raw_event_payload_json),
                            signature_verified,
                            processing_status,
                            received_ts_ms,
                            now_ts_ms,
                            now_ts_ms,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_contact_message_provider_events (
                            user_id,
                            contact_method_id,
                            provider_type,
                            channel_type,
                            provider_event_type,
                            provider_message_id,
                            provider_sender_handle,
                            provider_recipient_handle,
                            event_direction,
                            payload_hash,
                            raw_event_payload_json,
                            signature_verified,
                            processing_status,
                            event_received_at_ts_ms,
                            event_processed_at_ts_ms
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'inbound', %s, %s::jsonb, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            user_id,
                            contact_method_id,
                            provider_type,
                            channel_type,
                            provider_event_type,
                            normalized_provider_message_id,
                            provider_sender_handle,
                            provider_recipient_handle,
                            payload_hash,
                            psycopg2.extras.Json(raw_event_payload_json),
                            signature_verified,
                            processing_status,
                            received_ts_ms,
                            now_ts_ms,
                        ),
                    )

                stored_provider_event_id = cursor.fetchone()[0]
    except Exception as exc:
        raise RuntimeError("API_DCX_CONTACT_MESSAGE_PROVIDER_EVENT_STORE_FAILED") from exc

    return {
        "provider_event_id": stored_provider_event_id,
        "payload_hash": payload_hash,
    }


def _read_current_timestamp_ms() -> int:
    import time

    return int(time.time() * 1000)
