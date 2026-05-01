"""
CONTEXT:
This file reads one authenticated user market-topic detail payload.
It exists so the app can open the first AI-seeded topic detail view in Slice 1.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_authenticated_dcx_user_market_topic_detail(
    authenticated_user_id: int,
    market_topic_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
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
                        topic.topic_metadata_json,
                        topic.visibility_status,
                        forum_post.id AS forum_post_id,
                        forum_post.public_reference_code,
                        forum_post.visibility_status AS forum_visibility_status,
                        forum_post.forum_post_status,
                        topic.created_at_ts_ms,
                        topic.updated_at_ts_ms
                    FROM stephen_dcx_market_topics topic
                    LEFT JOIN stephen_dcx_forum_posts forum_post
                      ON forum_post.source_market_topic_id = topic.id
                     AND forum_post.forum_post_status IN ('open', 'closed')
                    WHERE topic.id = %s
                      AND topic.initiating_user_id = %s
                    LIMIT 1
                    """,
                    (market_topic_id, authenticated_user_id),
                )
                topic_row = cursor.fetchone()
                turn_rows = []
                if topic_row is not None:
                    cursor.execute(
                        """
                        SELECT
                            turn.id,
                            turn.turn_role,
                            turn.source_message_id,
                            turn.turn_text,
                            turn.turn_metadata_json,
                            turn.created_at_ts_ms
                        FROM stephen_dcx_market_topic_turns turn
                        WHERE turn.market_topic_id = %s
                        ORDER BY turn.created_at_ts_ms ASC, turn.id ASC
                        """,
                        (market_topic_id,),
                    )
                    turn_rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError("API_AUTHENTICATED_DCX_USER_MARKET_TOPIC_DETAIL_READ_FAILED") from exc

    if topic_row is None:
        return None

    return {
        "market_topic_id": topic_row[0],
        "source_message_id": topic_row[1],
        "topic_status": topic_row[2],
        "topic_title": topic_row[3],
        "topic_summary_text": topic_row[4],
        "topic_scope_text": topic_row[5],
        "topic_tags_json": topic_row[6] if isinstance(topic_row[6], list) else [],
        "topic_metadata_json": topic_row[7] if isinstance(topic_row[7], dict) else {},
        "visibility_status": topic_row[8] or "private",
        "forum_post_id": topic_row[9],
        "public_reference_code": topic_row[10],
        "forum_visibility_status": topic_row[11],
        "forum_post_status": topic_row[12],
        "created_at_ts_ms": topic_row[13],
        "updated_at_ts_ms": topic_row[14],
        "turns": [
            {
                "market_topic_turn_id": row[0],
                "turn_role": row[1],
                "source_message_id": row[2],
                "turn_text": row[3],
                "turn_metadata_json": row[4] if isinstance(row[4], dict) else {},
                "created_at_ts_ms": row[5],
            }
            for row in turn_rows
        ],
    }
