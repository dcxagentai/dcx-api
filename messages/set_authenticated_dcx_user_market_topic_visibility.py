"""
CONTEXT:
This file publishes, shares, or withdraws one authenticated user's market topic.
It exists for the MVP forum slice where a private trader-AI topic can be projected
into a public or shareable flat forum post.

CONTRACT:
preconditions:
- authenticated_user_id owns the source market topic.
- visibility_status is private, shareable, or public.
postconditions:
- the topic visibility is updated.
- private topics have no active/open forum projection.
- shareable/public topics have one open forum post projection.
side_effects:
- mutates stephen_dcx_market_topics and stephen_dcx_forum_posts.
idempotent: true for repeated calls with the same visibility.
retry_safe: true.
async_or_blocking: blocking database transaction.
idempotency_key: market_topic_id + visibility_status.
locks: SELECT FOR UPDATE on the topic row and active forum projection.
lock_strategy: serialize concurrent visibility changes on the topic row.

NARRATIVE:
WHY this exists: the private market topic is the trader's own AI workspace, while
the forum post is a public human discussion projection.
WHEN TO USE it: from the app topic detail view and later explicit cross-channel commands.
WHEN NOT TO USE it: not for adding comments or continuing AI chat.
WHAT CAN GO WRONG: invalid status, missing topic, or missing migration tables.
WHAT COMES NEXT: forum catalog/comment surfaces read from forum posts.

TESTS:
- No dedicated unit test exists yet. Smoke with PATCH /ai/chats/{id}/visibility.

ERRORS:
- API_DCX_MARKET_TOPIC_VISIBILITY_INVALID: retry with private, shareable, or public.
- API_DCX_MARKET_TOPIC_VISIBILITY_NOT_FOUND: refresh Topics and retry.
- API_DCX_MARKET_TOPIC_VISIBILITY_UPDATE_FAILED: retry after backend/database health is restored.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from storage.db_config import DB_CONFIG

DCX_MARKET_TOPIC_VISIBILITY_STATUSES = {"private", "shareable", "public"}


def set_authenticated_dcx_user_market_topic_visibility(
    authenticated_user_id: int,
    market_topic_id: int,
    visibility_status: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    normalized_visibility_status = (visibility_status or "").strip().lower()
    if normalized_visibility_status not in DCX_MARKET_TOPIC_VISIBILITY_STATUSES:
        raise RuntimeError("API_DCX_MARKET_TOPIC_VISIBILITY_INVALID")

    connect = connect_to_database or psycopg2.connect
    now_ts_ms = int(time.time() * 1000)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        topic.id,
                        topic.source_message_id,
                        topic.topic_title,
                        topic.topic_summary_text,
                        topic.topic_tags_json
                    FROM stephen_dcx_market_topics topic
                    WHERE topic.id = %s
                      AND topic.initiating_user_id = %s
                    FOR UPDATE
                    """,
                    (market_topic_id, authenticated_user_id),
                )
                topic_row = cursor.fetchone()
                if topic_row is None:
                    return None

                cursor.execute(
                    """
                    UPDATE stephen_dcx_market_topics
                    SET visibility_status = %s,
                        visibility_updated_at_ts_ms = %s,
                        updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (normalized_visibility_status, now_ts_ms, now_ts_ms, market_topic_id),
                )

                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_forum_posts
                    WHERE source_market_topic_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (market_topic_id,),
                )
                forum_post_row = cursor.fetchone()

                if normalized_visibility_status == "private":
                    if forum_post_row is not None:
                        cursor.execute(
                            """
                            UPDATE stephen_dcx_forum_posts
                            SET forum_post_status = 'withdrawn',
                                updated_at_ts_ms = %s
                            WHERE id = %s
                            """,
                            (now_ts_ms, forum_post_row[0]),
                        )
                    return {
                        "market_topic_id": market_topic_id,
                        "visibility_status": "private",
                        "forum_post_id": None,
                    }

                if forum_post_row is not None:
                    forum_post_id = forum_post_row[0]
                    cursor.execute(
                        """
                        UPDATE stephen_dcx_forum_posts
                        SET visibility_status = %s,
                            forum_post_status = 'open',
                            forum_title = %s,
                            forum_body_text = %s,
                            forum_tags_json = %s,
                            updated_at_ts_ms = %s
                        WHERE id = %s
                        """,
                        (
                            normalized_visibility_status,
                            topic_row[2] or "",
                            topic_row[3] or "",
                            Json(topic_row[4] if isinstance(topic_row[4], list) else []),
                            now_ts_ms,
                            forum_post_id,
                        ),
                    )
                else:
                    public_reference_code = f"Q{market_topic_id}"
                    share_token = f"topic_{uuid.uuid4().hex}"
                    cursor.execute(
                        """
                        INSERT INTO stephen_dcx_forum_posts (
                            source_market_topic_id,
                            owner_user_id,
                            source_message_id,
                            visibility_status,
                            forum_post_status,
                            public_reference_code,
                            share_token,
                            forum_title,
                            forum_body_text,
                            forum_tags_json,
                            forum_metadata_json,
                            created_at_ts_ms,
                            updated_at_ts_ms
                        )
                        VALUES (%s, %s, %s, %s, 'open', %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            market_topic_id,
                            authenticated_user_id,
                            topic_row[1],
                            normalized_visibility_status,
                            public_reference_code,
                            share_token,
                            topic_row[2] or "",
                            topic_row[3] or "",
                            Json(topic_row[4] if isinstance(topic_row[4], list) else []),
                            Json({}),
                            now_ts_ms,
                            now_ts_ms,
                        ),
                    )
                    forum_post_id = cursor.fetchone()[0]

        return {
            "market_topic_id": market_topic_id,
            "visibility_status": normalized_visibility_status,
            "forum_post_id": forum_post_id,
        }
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_MARKET_TOPIC_VISIBILITY_UPDATE_FAILED") from exc
