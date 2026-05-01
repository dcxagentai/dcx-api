"""
CONTEXT:
This file reads the public Market > Forum catalog for authenticated app users.
Forum posts are public projections of private market topics, with flat comments.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from storage.db_config import DB_CONFIG


def read_authenticated_dcx_market_forum_catalog(
    authenticated_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    if not isinstance(authenticated_user_id, int) or authenticated_user_id <= 0:
        raise RuntimeError("API_DCX_MARKET_FORUM_USER_NOT_FOUND")

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
                    raise RuntimeError("API_DCX_MARKET_FORUM_USER_NOT_FOUND")

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
                        forum_post.updated_at_ts_ms,
                        CASE
                          WHEN owner_user.public_identity_mode = 'anonymous' THEN 'Trader #' || owner_user.id::text
                          WHEN owner_user.public_identity_mode = 'handle' AND NULLIF(owner_user.public_handle, '') IS NOT NULL THEN '@' || owner_user.public_handle
                          WHEN NULLIF(owner_user.public_display_name, '') IS NOT NULL THEN owner_user.public_display_name
                          WHEN NULLIF(owner_user.public_handle, '') IS NOT NULL THEN '@' || owner_user.public_handle
                          ELSE 'Trader #' || owner_user.id::text
                        END AS owner_public_identity_label,
                        COUNT(comment.id) AS comment_count
                    FROM stephen_dcx_forum_posts forum_post
                    INNER JOIN stephen_dcx_users owner_user
                      ON owner_user.id = forum_post.owner_user_id
                    LEFT JOIN stephen_dcx_forum_comments comment
                      ON comment.forum_post_id = forum_post.id
                    WHERE forum_post.visibility_status = 'public'
                      AND forum_post.forum_post_status IN ('open', 'closed')
                    GROUP BY forum_post.id, owner_user.id
                    ORDER BY forum_post.updated_at_ts_ms DESC, forum_post.id DESC
                    """,
                )
                forum_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_MARKET_FORUM_CATALOG_READ_FAILED") from exc

    return {
        "forum_posts": [
            {
                "forum_post_id": row[0],
                "source_market_topic_id": row[1],
                "owner_user_id": row[2],
                "public_reference_code": row[3],
                "visibility_status": row[4],
                "forum_post_status": row[5],
                "forum_title": row[6],
                "forum_body_text": row[7],
                "forum_tags_json": row[8] if isinstance(row[8], list) else [],
                "updated_at_ts_ms": row[9],
                "owner_public_identity_label": row[10],
                "comment_count": row[11],
                "is_owned_by_authenticated_user": row[2] == authenticated_user_id,
            }
            for row in forum_rows
        ],
        "total_forum_post_count": len(forum_rows),
    }
