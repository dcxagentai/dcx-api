"""
CONTEXT:
This file reads the first authenticated Topics catalog payload for one DCX app user.
It exists so Slice 1 can project routed market-topic items into a dedicated user-visible list.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_authenticated_dcx_user_market_topics_catalog(
    authenticated_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MARKET_TOPICS_USER_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_users
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (authenticated_user_id,),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("API_AUTHENTICATED_DCX_USER_MARKET_TOPICS_USER_NOT_FOUND")

                cursor.execute(
                    """
                    SELECT
                        topic.id,
                        topic.source_message_id,
                        topic.topic_status,
                        topic.topic_title,
                        topic.topic_summary_text,
                        topic.topic_scope_text,
                        topic.topic_tags_json,
                        topic.updated_at_ts_ms,
                        message.channel_type,
                        message.created_at_ts_ms
                    FROM stephen_dcx_market_topics topic
                    INNER JOIN stephen_dcx_contact_messages message
                      ON message.id = topic.source_message_id
                    WHERE topic.initiating_user_id = %s
                    ORDER BY topic.updated_at_ts_ms DESC, topic.id DESC
                    """,
                    (authenticated_user_id,),
                )
                topic_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MARKET_TOPICS_CATALOG_READ_FAILED") from exc

    return {
        "market_topics": [
            {
                "market_topic_id": row[0],
                "source_message_id": row[1],
                "topic_status": row[2],
                "topic_title": row[3],
                "topic_summary_text": row[4],
                "topic_scope_text": row[5],
                "topic_tags_json": row[6] if isinstance(row[6], list) else [],
                "updated_at_ts_ms": row[7],
                "source_channel_type": row[8],
                "source_created_at_ts_ms": row[9],
            }
            for row in topic_rows
        ],
        "total_market_topic_count": len(topic_rows),
    }
