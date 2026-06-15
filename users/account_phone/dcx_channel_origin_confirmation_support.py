"""
CONTEXT:
This file owns the small channel-origin confirmation layer for user contact methods.
It exists so "this user owns this phone" can stay separate from "this user has confirmed
the currently active DCX WhatsApp sender number".
"""

from __future__ import annotations

import os
from typing import Any

import psycopg2.extras

DCX_CHANNEL_TYPE_WHATSAPP = "whatsapp"
DCX_PROVIDER_TYPE_META_WHATSAPP = "meta_whatsapp"
DCX_CONFIRMATION_PURPOSE_CONTACT_VERIFICATION = "contact_verification"
DCX_CONFIRMATION_PURPOSE_SENDER_RECONFIRMATION = "sender_reconfirmation"


def read_dcx_contact_method_confirmation_purpose(raw_purpose: str | None) -> str:
    normalized_purpose = raw_purpose.strip().lower() if isinstance(raw_purpose, str) else ""
    if normalized_purpose == DCX_CONFIRMATION_PURPOSE_SENDER_RECONFIRMATION:
        return DCX_CONFIRMATION_PURPOSE_SENDER_RECONFIRMATION

    return DCX_CONFIRMATION_PURPOSE_CONTACT_VERIFICATION


def ensure_current_dcx_meta_whatsapp_channel_origin(
    cursor: Any,
    now_ts_ms: int,
) -> dict:
    """
    Minimal contract:
      - Upserts the currently configured Meta WhatsApp sender as a DCX channel origin.
      - In local/dev, missing Meta sender config falls back to a stable local placeholder.
    """
    environment_key = _read_dcx_environment_key()
    provider_sender_id = os.getenv("META_PHONE_NUMBER_ID", "").strip()
    if provider_sender_id == "":
        if environment_key in {"production", "staging"}:
            raise RuntimeError("API_DCX_CHANNEL_ORIGIN_CONFIGURATION_MISSING:META_PHONE_NUMBER_ID")
        provider_sender_id = f"{environment_key}:meta_whatsapp_default"

    provider_account_id = (
        os.getenv("META_WHATSAPP_BUSINESS_ACCOUNT_ID", "").strip()
        or os.getenv("META_WABA_ID", "").strip()
    )
    sender_display_handle = (
        os.getenv("META_WHATSAPP_DISPLAY_PHONE_NUMBER", "").strip()
        or os.getenv("META_WHATSAPP_DISPLAY_HANDLE", "").strip()
    )
    sender_display_name = (
        os.getenv("META_WHATSAPP_BUSINESS_DISPLAY_NAME", "").strip()
        or os.getenv("META_WHATSAPP_DISPLAY_NAME", "").strip()
    )

    cursor.execute(
        """
        INSERT INTO stephen_dcx_channel_origins (
            channel_type,
            provider_type,
            provider_account_id,
            provider_sender_id,
            sender_display_handle,
            sender_display_name,
            environment_key,
            origin_status,
            activated_at_ts_ms,
            retired_at_ts_ms,
            origin_metadata_json,
            created_at_ts_ms,
            updated_at_ts_ms
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s::jsonb, %s, %s)
        ON CONFLICT (
            channel_type,
            provider_type,
            provider_sender_id,
            environment_key
        )
        DO UPDATE
        SET
            provider_account_id = EXCLUDED.provider_account_id,
            sender_display_handle = EXCLUDED.sender_display_handle,
            sender_display_name = EXCLUDED.sender_display_name,
            origin_status = 'active',
            retired_at_ts_ms = NULL,
            origin_metadata_json = stephen_dcx_channel_origins.origin_metadata_json || EXCLUDED.origin_metadata_json,
            updated_at_ts_ms = EXCLUDED.updated_at_ts_ms
        RETURNING
            id,
            channel_type,
            provider_type,
            provider_account_id,
            provider_sender_id,
            sender_display_handle,
            sender_display_name,
            environment_key,
            origin_status
        """,
        (
            DCX_CHANNEL_TYPE_WHATSAPP,
            DCX_PROVIDER_TYPE_META_WHATSAPP,
            provider_account_id,
            provider_sender_id,
            sender_display_handle,
            sender_display_name,
            environment_key,
            "active",
            now_ts_ms,
            psycopg2.extras.Json(
                {
                    "source": "runtime_env",
                    "meta_api_version": os.getenv("META_API_VERSION", "").strip(),
                }
            ),
            now_ts_ms,
            now_ts_ms,
        ),
    )
    origin_row = cursor.fetchone()
    if origin_row is None:
        raise RuntimeError("API_DCX_CHANNEL_ORIGIN_PERSISTENCE_FAILED")

    return _build_channel_origin_dict(origin_row)


def read_confirmed_contact_method_channel_origin_confirmation(
    cursor: Any,
    contact_method_id: int,
    channel_origin_id: int,
) -> dict | None:
    cursor.execute(
        """
        SELECT
            id,
            confirmation_status,
            confirmed_at_ts_ms
        FROM stephen_dcx_contact_method_channel_confirmations
        WHERE contact_method_id = %s
          AND channel_origin_id = %s
          AND confirmation_status = %s
          AND confirmed_at_ts_ms IS NOT NULL
        ORDER BY confirmed_at_ts_ms DESC, id DESC
        LIMIT 1
        """,
        (
            contact_method_id,
            channel_origin_id,
            "confirmed",
        ),
    )
    confirmation_row = cursor.fetchone()
    if confirmation_row is None:
        return None

    return {
        "id": confirmation_row[0],
        "confirmation_status": confirmation_row[1],
        "confirmed_at_ts_ms": confirmation_row[2],
    }


def insert_pending_contact_method_channel_origin_confirmation(
    cursor: Any,
    user_id: int,
    contact_method_id: int,
    channel_origin_id: int,
    auth_challenge_id: int,
    confirmation_purpose: str,
    expires_at_ts_ms: int,
    now_ts_ms: int,
) -> int:
    cursor.execute(
        """
        UPDATE stephen_dcx_contact_method_channel_confirmations
        SET
            confirmation_status = %s,
            updated_at_ts_ms = %s
        WHERE user_id = %s
          AND contact_method_id = %s
          AND channel_origin_id = %s
          AND confirmation_status IN ('pending', 'sent')
        """,
        (
            "invalidated",
            now_ts_ms,
            user_id,
            contact_method_id,
            channel_origin_id,
        ),
    )
    cursor.execute(
        """
        INSERT INTO stephen_dcx_contact_method_channel_confirmations (
            user_id,
            contact_method_id,
            channel_origin_id,
            auth_challenge_id,
            confirmation_purpose,
            confirmation_status,
            expires_at_ts_ms,
            created_at_ts_ms,
            updated_at_ts_ms
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            user_id,
            contact_method_id,
            channel_origin_id,
            auth_challenge_id,
            confirmation_purpose,
            "pending",
            expires_at_ts_ms,
            now_ts_ms,
            now_ts_ms,
        ),
    )
    confirmation_row = cursor.fetchone()
    if confirmation_row is None:
        raise RuntimeError("API_DCX_CHANNEL_ORIGIN_CONFIRMATION_PERSISTENCE_FAILED")

    return confirmation_row[0]


def mark_contact_method_channel_origin_confirmation_sent(
    cursor: Any,
    user_id: int,
    auth_challenge_id: int,
    provider_message_id: str | None,
    template_name: str | None,
    template_language_code: str | None,
    sent_at_ts_ms: int,
) -> None:
    cursor.execute(
        """
        UPDATE stephen_dcx_contact_method_channel_confirmations
        SET
            confirmation_status = %s,
            provider_message_id = NULLIF(%s, ''),
            template_name = %s,
            template_language_code = %s,
            sent_at_ts_ms = %s,
            updated_at_ts_ms = %s
        WHERE user_id = %s
          AND auth_challenge_id = %s
          AND confirmation_status = %s
        """,
        (
            "sent",
            (provider_message_id or "").strip(),
            (template_name or "").strip(),
            (template_language_code or "").strip(),
            sent_at_ts_ms,
            sent_at_ts_ms,
            user_id,
            auth_challenge_id,
            "pending",
        ),
    )


def mark_contact_method_channel_origin_confirmation_confirmed(
    cursor: Any,
    user_id: int,
    auth_challenge_id: int,
    contact_method_id: int,
    confirmed_at_ts_ms: int,
) -> None:
    cursor.execute(
        """
        UPDATE stephen_dcx_contact_method_channel_confirmations
        SET
            contact_method_id = %s,
            confirmation_status = %s,
            confirmed_at_ts_ms = %s,
            updated_at_ts_ms = %s
        WHERE user_id = %s
          AND auth_challenge_id = %s
          AND confirmation_status IN ('pending', 'sent')
        """,
        (
            contact_method_id,
            "confirmed",
            confirmed_at_ts_ms,
            confirmed_at_ts_ms,
            user_id,
            auth_challenge_id,
        ),
    )


def mark_contact_method_channel_origin_confirmation_terminal(
    cursor: Any,
    user_id: int,
    auth_challenge_id: int,
    confirmation_status: str,
    now_ts_ms: int,
) -> None:
    cursor.execute(
        """
        UPDATE stephen_dcx_contact_method_channel_confirmations
        SET
            confirmation_status = %s,
            updated_at_ts_ms = %s
        WHERE user_id = %s
          AND auth_challenge_id = %s
          AND confirmation_status IN ('pending', 'sent')
        """,
        (
            confirmation_status,
            now_ts_ms,
            user_id,
            auth_challenge_id,
        ),
    )


def _read_dcx_environment_key() -> str:
    return os.getenv("DCX_ENVIRONMENT", "local").strip().lower() or "local"


def _build_channel_origin_dict(origin_row: tuple) -> dict:
    return {
        "id": origin_row[0],
        "channel_type": origin_row[1],
        "provider_type": origin_row[2],
        "provider_account_id": origin_row[3],
        "provider_sender_id": origin_row[4],
        "sender_display_handle": origin_row[5],
        "sender_display_name": origin_row[6],
        "environment_key": origin_row[7],
        "origin_status": origin_row[8],
    }
