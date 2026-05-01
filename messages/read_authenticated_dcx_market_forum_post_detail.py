"""
CONTEXT:
This file reads one public/shareable forum post and its flat comment list.
It supports the MVP Market > Forum detail panel.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_authenticated_dcx_market_forum_post_detail(
    authenticated_user_id: int,
    forum_post_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        forum_post.id,
                        forum_post.source_market_topic_id,
                        forum_post.owner_user_id,
                        forum_post.public_reference_code,
                        forum_post.visibility_status,
                        forum_post.forum_post_status,
                        forum_post.forum_title,
                        forum_post.forum_body_text,
                        forum_post.forum_tags_json,
                        forum_post.created_at_ts_ms,
                        forum_post.updated_at_ts_ms,
                        CASE
                          WHEN owner_user.public_identity_mode = 'anonymous' THEN 'Trader #' || owner_user.id::text
                          WHEN owner_user.public_identity_mode = 'handle' AND NULLIF(owner_user.public_handle, '') IS NOT NULL THEN '@' || owner_user.public_handle
                          WHEN NULLIF(owner_user.public_display_name, '') IS NOT NULL THEN owner_user.public_display_name
                          WHEN NULLIF(owner_user.public_handle, '') IS NOT NULL THEN '@' || owner_user.public_handle
                          ELSE 'Trader #' || owner_user.id::text
                        END AS owner_public_identity_label
                    FROM stephen_dcx_forum_posts forum_post
                    INNER JOIN stephen_dcx_users owner_user
                      ON owner_user.id = forum_post.owner_user_id
                    WHERE forum_post.id = %s
                      AND forum_post.visibility_status IN ('shareable', 'public')
                      AND forum_post.forum_post_status IN ('open', 'closed')
                    LIMIT 1
                    """,
                    (forum_post_id,),
                )
                forum_post_row = cursor.fetchone()
                comment_rows = []
                if forum_post_row is not None:
                    cursor.execute(
                        """
                        SELECT
                            comment.id,
                            comment.author_user_id,
                            comment.comment_text,
                            comment.language_code,
                            comment.comment_summary_text,
                            comment.created_at_ts_ms,
                            comment.updated_at_ts_ms,
                            CASE
                              WHEN author_user.public_identity_mode = 'anonymous' THEN 'Trader #' || author_user.id::text
                              WHEN author_user.public_identity_mode = 'handle' AND NULLIF(author_user.public_handle, '') IS NOT NULL THEN '@' || author_user.public_handle
                              WHEN NULLIF(author_user.public_display_name, '') IS NOT NULL THEN author_user.public_display_name
                              WHEN NULLIF(author_user.public_handle, '') IS NOT NULL THEN '@' || author_user.public_handle
                              ELSE 'Trader #' || author_user.id::text
                            END AS author_public_identity_label
                        FROM stephen_dcx_forum_comments comment
                        INNER JOIN stephen_dcx_users author_user
                          ON author_user.id = comment.author_user_id
                        WHERE comment.forum_post_id = %s
                        ORDER BY comment.created_at_ts_ms ASC, comment.id ASC
                        """,
                        (forum_post_id,),
                    )
                    comment_rows = cursor.fetchall()
    except Exception as exc:
        raise RuntimeError("API_DCX_MARKET_FORUM_POST_DETAIL_READ_FAILED") from exc

    if forum_post_row is None:
        return None

    return {
        "forum_post_id": forum_post_row[0],
        "source_market_topic_id": forum_post_row[1],
        "owner_user_id": forum_post_row[2],
        "public_reference_code": forum_post_row[3],
        "visibility_status": forum_post_row[4],
        "forum_post_status": forum_post_row[5],
        "forum_title": forum_post_row[6],
        "forum_body_text": forum_post_row[7],
        "forum_tags_json": forum_post_row[8] if isinstance(forum_post_row[8], list) else [],
        "created_at_ts_ms": forum_post_row[9],
        "updated_at_ts_ms": forum_post_row[10],
        "owner_public_identity_label": forum_post_row[11],
        "is_owned_by_authenticated_user": forum_post_row[2] == authenticated_user_id,
        "comments": [
            {
                "forum_comment_id": row[0],
                "author_user_id": row[1],
                "comment_text": row[2],
                "language_code": row[3],
                "comment_summary_text": row[4],
                "created_at_ts_ms": row[5],
                "updated_at_ts_ms": row[6],
                "author_public_identity_label": row[7],
                "is_owned_by_authenticated_user": row[1] == authenticated_user_id,
            }
            for row in comment_rows
        ],
    }
