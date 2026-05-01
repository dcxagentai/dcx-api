"""
CONTEXT:
This file appends one flat comment to a public/shareable forum post.
It is intentionally simple for MVP: no nested replies, no AI shaping yet.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from storage.db_config import DB_CONFIG


def append_authenticated_dcx_forum_comment(
    authenticated_user_id: int,
    forum_post_id: int,
    comment_text: str,
    language_code: str = "en",
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    normalized_comment_text = (comment_text or "").strip()
    if not normalized_comment_text:
        raise RuntimeError("API_DCX_FORUM_COMMENT_EMPTY")

    normalized_language_code = (language_code or "en").strip().lower() or "en"
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = int(time.time() * 1000)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM stephen_dcx_forum_posts
                    WHERE id = %s
                      AND visibility_status IN ('shareable', 'public')
                      AND forum_post_status = 'open'
                    LIMIT 1
                    """,
                    (forum_post_id,),
                )
                if cursor.fetchone() is None:
                    return None

                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_forum_comments (
                        forum_post_id,
                        author_user_id,
                        comment_text,
                        language_code,
                        comment_summary_text,
                        comment_metadata_json,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, %s, %s, %s, '', %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        forum_post_id,
                        authenticated_user_id,
                        normalized_comment_text,
                        normalized_language_code,
                        Json({}),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                forum_comment_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    UPDATE stephen_dcx_forum_posts
                    SET updated_at_ts_ms = %s
                    WHERE id = %s
                    """,
                    (now_ts_ms, forum_post_id),
                )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_FORUM_COMMENT_APPEND_FAILED") from exc

    return {
        "forum_comment_id": forum_comment_id,
        "forum_post_id": forum_post_id,
        "author_user_id": authenticated_user_id,
        "comment_text": normalized_comment_text,
        "language_code": normalized_language_code,
        "created_at_ts_ms": now_ts_ms,
        "updated_at_ts_ms": now_ts_ms,
    }
