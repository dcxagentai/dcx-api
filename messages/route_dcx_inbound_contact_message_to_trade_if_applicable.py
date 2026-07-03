from __future__ import annotations

from typing import Any, Callable

import psycopg2

from messages.append_authenticated_dcx_trade_thread_message import (
    append_authenticated_dcx_trade_thread_message,
)
from messages.dcx_inbound_cross_surface_reference_text import (
    build_dcx_cross_surface_routed_message_text,
    extract_dcx_cross_surface_reference_code,
)
from messages.mark_dcx_contact_message_cross_surface_reference_route import (
    mark_dcx_contact_message_cross_surface_reference_routed,
)
from messages.send_dcx_trade_thread_message_notification import (
    upsert_dcx_trade_thread_participant_route,
)
from messages.start_authenticated_dcx_trade_thread_from_market_trade import (
    start_authenticated_dcx_trade_thread_from_market_trade,
)
from storage.db_config import DB_CONFIG


def route_dcx_inbound_contact_message_to_trade_if_applicable(
    contact_message_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    connect = connect_to_database or psycopg2.connect

    try:
        message_context = _read_inbound_contact_message_trade_route_context(
            connect=connect,
            contact_message_id=contact_message_id,
        )
        if message_context is None:
            return None
        if message_context["user_id"] is None or message_context["source_contact_is_verified"] is not True:
            return None

        trade_reference_code = extract_dcx_cross_surface_reference_code(
            text=f"{message_context['message_subject']}\n{message_context['raw_text_content']}",
            reference_prefix="T",
        )
        if trade_reference_code is None:
            return None

        trade_publication_context = _read_referenced_trade_publication(
            connect=connect,
            trade_reference_code=trade_reference_code,
        )
        if trade_publication_context is None:
            return None
        if trade_publication_context["owner_user_id"] == message_context["user_id"]:
            return None

        thread_context = start_authenticated_dcx_trade_thread_from_market_trade(
            authenticated_user_id=message_context["user_id"],
            trade_publication_id=trade_publication_context["trade_publication_id"],
            connect_to_database=connect,
        )
        if thread_context is None:
            return None

        existing_thread_message_id = _read_existing_thread_message_id_for_contact_message(
            connect=connect,
            contact_message_id=contact_message_id,
        )
        if existing_thread_message_id is None:
            routed_message_text = build_dcx_cross_surface_routed_message_text(
                message_subject=message_context["message_subject"],
                message_text=message_context["raw_text_content"],
                reference_code=trade_reference_code,
                include_subject=message_context["channel_type"] == "email",
            )
            if routed_message_text == "":
                return None

            upsert_dcx_trade_thread_participant_route(
                trade_thread_id=thread_context["trade_thread_id"],
                user_id=message_context["user_id"],
                current_route_channel=message_context["channel_type"],
                current_route_contact_method_id=message_context["contact_method_id"],
                route_source="latest_reply",
                connect_to_database=connect,
            )
            append_authenticated_dcx_trade_thread_message(
                authenticated_user_id=message_context["user_id"],
                trade_thread_id=thread_context["trade_thread_id"],
                message_text=routed_message_text,
                language_code=message_context["preferred_language_code"],
                source_channel_type=message_context["channel_type"],
                source_contact_message_id=contact_message_id,
                notify_other_participant=True,
                connect_to_database=connect,
            )
            existing_thread_message_id = _read_existing_thread_message_id_for_contact_message(
                connect=connect,
                contact_message_id=contact_message_id,
            )

        marker_result = mark_dcx_contact_message_cross_surface_reference_routed(
            contact_message_id=contact_message_id,
            reference_kind="trade",
            reference_code=trade_reference_code,
            route_summary_text=f"Routed trade reference {trade_reference_code} to trade chat {thread_context['thread_reference_code']}.",
            route_metadata_json={
                "trade_id": trade_publication_context["trade_id"],
                "trade_publication_id": trade_publication_context["trade_publication_id"],
                "trade_thread_id": thread_context["trade_thread_id"],
                "thread_reference_code": thread_context["thread_reference_code"],
                "trade_thread_message_id": existing_thread_message_id,
            },
            connect_to_database=connect,
        )
    except Exception as exc:
        raise RuntimeError("API_DCX_INBOUND_TRADE_ROUTE_FAILED") from exc

    return {
        **marker_result,
        "trade_id": trade_publication_context["trade_id"],
        "trade_publication_id": trade_publication_context["trade_publication_id"],
        "trade_thread_id": thread_context["trade_thread_id"],
        "thread_reference_code": thread_context["thread_reference_code"],
        "trade_thread_message_id": existing_thread_message_id,
    }


def _read_inbound_contact_message_trade_route_context(
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


def _read_referenced_trade_publication(
    connect: Callable[..., Any],
    trade_reference_code: str,
) -> dict | None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, trade_id, owner_user_id
                FROM stephen_dcx_trade_publications
                WHERE lower(public_reference_code) = lower(%s)
                  AND publication_status = 'active'
                  AND visibility_status IN ('shareable', 'public')
                LIMIT 1
                """,
                (trade_reference_code,),
            )
            row = cursor.fetchone()
    if row is None:
        return None
    return {
        "trade_publication_id": row[0],
        "trade_id": row[1],
        "owner_user_id": row[2],
    }


def _read_existing_thread_message_id_for_contact_message(
    connect: Callable[..., Any],
    contact_message_id: int,
) -> int | None:
    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM stephen_dcx_trade_thread_messages
                WHERE source_contact_message_id = %s
                ORDER BY id ASC
                LIMIT 1
                """,
                (contact_message_id,),
            )
            row = cursor.fetchone()
    return row[0] if row is not None else None
