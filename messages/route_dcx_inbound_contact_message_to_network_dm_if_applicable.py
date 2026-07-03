from __future__ import annotations

from typing import Any, Callable

import psycopg2

from messages.dcx_inbound_cross_surface_reference_text import (
    build_dcx_cross_surface_routed_message_text,
    extract_dcx_cross_surface_reference_code,
    read_dcx_cross_surface_reference_id,
)
from messages.mark_dcx_contact_message_cross_surface_reference_route import (
    mark_dcx_contact_message_cross_surface_reference_routed,
)
from network.dcx_network_capabilities import append_authenticated_dcx_network_dm_message
from storage.db_config import DB_CONFIG


def route_dcx_inbound_contact_message_to_network_dm_if_applicable(
    contact_message_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    connect = connect_to_database or psycopg2.connect

    try:
        message_context = _read_inbound_contact_message_network_dm_route_context(
            connect=connect,
            contact_message_id=contact_message_id,
        )
        if message_context is None:
            return None
        if message_context["user_id"] is None or message_context["source_contact_is_verified"] is not True:
            return None

        dm_reference_code = extract_dcx_cross_surface_reference_code(
            text=f"{message_context['message_subject']}\n{message_context['raw_text_content']}",
            reference_prefix="DM",
        )
        if dm_reference_code is None:
            return None
        dm_thread_id = read_dcx_cross_surface_reference_id(
            reference_code=dm_reference_code,
            reference_prefix="DM",
        )
        if dm_thread_id is None:
            return None

        routed_message_text = build_dcx_cross_surface_routed_message_text(
            message_subject=message_context["message_subject"],
            message_text=message_context["raw_text_content"],
            reference_code=dm_reference_code,
            include_subject=message_context["channel_type"] == "email",
        )
        if routed_message_text == "":
            return None

        try:
            dm_thread_payload = append_authenticated_dcx_network_dm_message(
                authenticated_user_id=message_context["user_id"],
                dm_thread_id=dm_thread_id,
                message_text=routed_message_text,
                language_code=message_context["preferred_language_code"],
                source_channel_type=message_context["channel_type"],
                source_contact_message_id=contact_message_id,
                connect_to_database=connect,
            )
        except RuntimeError as append_error:
            if str(append_error) in {
                "API_DCX_NETWORK_CONTENT_PROHIBITED",
                "API_DCX_NETWORK_DM_MESSAGE_INVALID",
                "API_DCX_NETWORK_DM_NOT_FOUND",
            }:
                return None
            raise
        if dm_thread_payload is None:
            return None

        marker_result = mark_dcx_contact_message_cross_surface_reference_routed(
            contact_message_id=contact_message_id,
            reference_kind="dm",
            reference_code=dm_reference_code,
            route_summary_text=f"Routed to network DM {dm_reference_code}.",
            route_metadata_json={
                "dm_thread_id": dm_thread_id,
                "thread_reference_code": dm_thread_payload.get("thread_reference_code", dm_reference_code),
            },
            connect_to_database=connect,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_INBOUND_NETWORK_DM_ROUTE_FAILED") from exc

    return {
        **marker_result,
        "dm_thread_id": dm_thread_id,
        "thread_reference_code": dm_thread_payload.get("thread_reference_code", dm_reference_code),
    }


def _read_inbound_contact_message_network_dm_route_context(
    connect: Callable[..., Any],
    contact_message_id: int,
) -> dict | None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    message.id,
                    message.user_id,
                    message.contact_method_id,
                    message.channel_type,
                    message.message_subject,
                    message.raw_text_content,
                    message.message_metadata_json,
                    COALESCE(language.language_code, 'en') AS preferred_language_code
                FROM stephen_dcx_contact_messages message
                LEFT JOIN stephen_dcx_users user_row
                  ON user_row.id = message.user_id
                LEFT JOIN stephen_dcx_languages language
                  ON language.id = user_row.preferred_language_id
                WHERE message.id = %s
                  AND message.message_direction = 'inbound'
                  AND message.channel_type IN ('email', 'whatsapp')
                LIMIT 1
                """,
                (contact_message_id,),
            )
            row = cursor.fetchone()

    if row is None:
        return None
    return {
        "message_id": row[0],
        "user_id": row[1],
        "contact_method_id": row[2],
        "channel_type": row[3],
        "message_subject": row[4] or "",
        "raw_text_content": row[5] or "",
        "source_contact_is_verified": (
            row[6].get("source_contact_is_verified") is True
            if isinstance(row[6], dict)
            else False
        ),
        "preferred_language_code": row[7] or "en",
    }
