"""
CONTEXT:
This file owns the first app-private DCX Network capabilities.
It backs profiles, follows, a simple network feed, and direct messages without replacing
Trade Chats or exposing public web/SEO surfaces yet.
"""

from __future__ import annotations

import re
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from apis.gemini.generate_dcx_gemini_user_content_policy_check import (
    generate_dcx_gemini_user_content_policy_check,
)
from apis.gemini.translate_dcx_gemini_trade_thread_message import (
    translate_dcx_gemini_trade_thread_message,
)
from storage.db_config import DB_CONFIG

NETWORK_HANDLE_PATTERN = re.compile(r"^[a-z0-9_]{3,32}$")
NETWORK_RESERVED_HANDLES = {
    "feed",
    "dms",
    "settings",
    "admin",
    "me",
    "new",
    "trades",
    "ai",
    "login",
    "logout",
    "profile",
    "profiles",
}
NETWORK_FEED_SCOPES = {"following", "all"}
NETWORK_TEXT_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8})?$")


def read_authenticated_dcx_network_profile(
    authenticated_user_id: int,
    network_nickname: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id is one signed-in DCX user id.
        - network_nickname is the lowercase public handle segment from `/network/{nickname}`.
        - The configured database is reachable.
      postconditions:
        - Returns one profile payload, badges, follow state, DM permission, and recent posts.
        - Returns null when no profile uses that nickname.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The new network layer needs a compact trader profile that turns the language,
          country, timezone, and commodity preferences into useful social badges.
      WHEN TO USE it:
        - Use it when rendering `/network/{nickname}` or refreshing a follow/DM action outcome.
      WHEN NOT TO USE it:
        - Do not use it for admin user search, CRM import, or unauthenticated public SEO pages.
      WHAT CAN GO WRONG:
        - The nickname can be missing, malformed, reserved, or not found.
        - Database reads can fail.
      WHAT COMES NEXT:
        - Add proper image upload/crop and public-facing Astro projections later.

    TESTS:
      - No dedicated network tests exist yet; route smoke and TypeScript compile cover this first slice.

    ERRORS:
      - API_DCX_NETWORK_PROFILE_READ_FAILED:
          suggested_action: Retry after confirming database health.
          common_causes:
            - database unavailable
            - schema migration not applied
          recovery_steps:
            - Apply the network migration locally/live.
            - Retry after backend health is restored.
          retry_safe: true

    CODE:
    """
    normalized_nickname = normalize_dcx_network_nickname(network_nickname)
    if normalized_nickname is None:
        return None

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                profile_row = _read_network_user_profile_row(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    network_nickname=normalized_nickname,
                )
                if profile_row is None:
                    return None

                profile_payload = _read_network_profile_payload_from_row(profile_row)
                profile_user_id = profile_payload["user_id"]
                profile_payload["is_self"] = profile_user_id == authenticated_user_id
                if profile_payload["is_self"]:
                    profile_payload["can_dm"] = False
                profile_payload.update(_read_network_badges_for_user(cursor, profile_user_id))
                profile_payload["recent_posts"] = _read_network_recent_posts_for_profile(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    profile_user_id=profile_user_id,
                )
                return profile_payload
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NETWORK_PROFILE_READ_FAILED") from exc


def set_authenticated_dcx_network_follow(
    authenticated_user_id: int,
    network_nickname: str,
    should_follow: bool,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id is one signed-in DCX user id.
        - network_nickname identifies another DCX user with a public handle.
        - should_follow declares the desired active follow state.
      postconditions:
        - Upserts one follow row as active or inactive.
        - Returns the refreshed profile payload for the followed/unfollowed user.
      side_effects:
        - writes one row in `stephen_dcx_network_follows`
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: network_follow:{authenticated_user_id}:{network_nickname}:{should_follow}
      locks:
        - unique index lock on `stephen_dcx_network_follows(follower_user_id, followed_user_id)`
      contention_strategy: rely on the unique pair upsert so repeated clicks converge on the requested state

    NARRATIVE:
      WHY this exists:
        - Following gives the network feed a user-controlled default and gives profiles a visible
          early trust/reputation signal.
      WHEN TO USE it:
        - Use it from profile follow/unfollow buttons.
      WHEN NOT TO USE it:
        - Do not use it as a block/mute system; those are separate social safety mechanics.
      WHAT CAN GO WRONG:
        - The target profile may not exist.
        - The user may try to follow themselves.
      WHAT COMES NEXT:
        - Add blocks/mutes and notification fanout once the base network is exercised.

    TESTS:
      - No dedicated network tests exist yet; route smoke and TypeScript compile cover this first slice.

    ERRORS:
      - API_DCX_NETWORK_PROFILE_NOT_FOUND:
          suggested_action: Refresh the profile URL and retry with a valid nickname.
          common_causes:
            - stale nickname
            - malformed nickname
          recovery_steps:
            - Open the current profile from the network feed.
          retry_safe: true
      - API_DCX_NETWORK_FOLLOW_SELF:
          suggested_action: Follow another trader instead.
          common_causes:
            - user opened their own profile and clicked follow
          recovery_steps:
            - No recovery needed.
          retry_safe: true

    CODE:
    """
    normalized_nickname = normalize_dcx_network_nickname(network_nickname)
    if normalized_nickname is None:
        raise RuntimeError("API_DCX_NETWORK_PROFILE_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                profile_row = _read_network_user_profile_row(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    network_nickname=normalized_nickname,
                )
                if profile_row is None:
                    raise RuntimeError("API_DCX_NETWORK_PROFILE_NOT_FOUND")

                profile_user_id = int(profile_row[0])
                if profile_user_id == authenticated_user_id:
                    raise RuntimeError("API_DCX_NETWORK_FOLLOW_SELF")

                cursor.execute(
                    """
                    INSERT INTO public.stephen_dcx_network_follows (
                        follower_user_id,
                        followed_user_id,
                        follow_status
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (follower_user_id, followed_user_id) DO UPDATE
                    SET
                        follow_status = EXCLUDED.follow_status,
                        updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
                    """,
                    (
                        authenticated_user_id,
                        profile_user_id,
                        "active" if should_follow else "inactive",
                    ),
                )

                refreshed_row = _read_network_user_profile_row(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    network_nickname=normalized_nickname,
                )
                if refreshed_row is None:
                    raise RuntimeError("API_DCX_NETWORK_PROFILE_NOT_FOUND")
                profile_payload = _read_network_profile_payload_from_row(refreshed_row)
                profile_payload["is_self"] = profile_user_id == authenticated_user_id
                if profile_payload["is_self"]:
                    profile_payload["can_dm"] = False
                profile_payload.update(_read_network_badges_for_user(cursor, profile_user_id))
                profile_payload["recent_posts"] = _read_network_recent_posts_for_profile(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    profile_user_id=profile_user_id,
                )
                return profile_payload
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NETWORK_FOLLOW_SAVE_FAILED") from exc


def read_authenticated_dcx_network_feed(
    authenticated_user_id: int,
    feed_scope: str = "following",
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id is one signed-in DCX user id.
        - feed_scope is either `following` or `all`.
      postconditions:
        - Returns app-private network posts and one-level replies.
        - Defaults to people the user follows plus the user's own posts.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The feed gives commodity traders small public actions and lightweight social signals
          before any promise of immediate large-market liquidity.
      WHEN TO USE it:
        - Use it for `/network/feed` with Following/All scope controls.
      WHEN NOT TO USE it:
        - Do not use it for public unauthenticated SEO pages yet.
      WHAT CAN GO WRONG:
        - The network migration may not be applied.
      WHAT COMES NEXT:
        - Add notification fanout, translations, and optional public projections later.

    TESTS:
      - No dedicated network tests exist yet; route smoke and TypeScript compile cover this first slice.

    ERRORS:
      - API_DCX_NETWORK_FEED_READ_FAILED:
          suggested_action: Retry after confirming database health.
          common_causes:
            - database unavailable
            - schema migration not applied
          recovery_steps:
            - Apply the migration and retry.
          retry_safe: true

    CODE:
    """
    normalized_scope = feed_scope.strip().lower() if isinstance(feed_scope, str) else "following"
    if normalized_scope not in NETWORK_FEED_SCOPES:
        normalized_scope = "following"

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    _build_network_feed_posts_query(normalized_scope),
                    (authenticated_user_id,),
                )
                post_rows = cursor.fetchall()
                post_ids = [row[0] for row in post_rows]
                reply_rows_by_post_id = _read_network_reply_rows_by_post_id(cursor, post_ids)

                posts = [
                    _read_network_feed_post_payload(
                        post_row=post_row,
                        reply_rows=reply_rows_by_post_id.get(post_row[0], []),
                        viewer_user_id=authenticated_user_id,
                    )
                    for post_row in post_rows
                ]

                return {
                    "scope": normalized_scope,
                    "posts": posts,
                    "total_post_count": len(posts),
                }
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NETWORK_FEED_READ_FAILED") from exc


def create_authenticated_dcx_network_feed_post(
    authenticated_user_id: int,
    post_text: str,
    language_code: str = "en",
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id is one signed-in DCX user id with a public nickname.
        - post_text is 1-500 characters after trimming.
        - language_code is one normalized language code.
      postconditions:
        - Stores one active app-public network feed post.
        - Blocks prohibited content before persistence.
      side_effects:
        - writes one row in `stephen_dcx_network_feed_posts`
        - may call Gemini for content policy
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks: []
      contention_strategy: each submit intentionally creates one new post

    NARRATIVE:
      WHY this exists:
        - Public network posts create lightweight habit and reputation loops without forcing
          every interaction into a trade object.
      WHEN TO USE it:
        - Use it from the explicit “New post” composer on the network feed.
      WHEN NOT TO USE it:
        - Do not use it for private DMs or structured Trade Chats.
      WHAT CAN GO WRONG:
        - The user may not have chosen a nickname.
        - The post may be empty, too long, or prohibited.
      WHAT COMES NEXT:
        - Add all-13-language translation jobs for feed posts.

    TESTS:
      - No dedicated network tests exist yet; route smoke and TypeScript compile cover this first slice.

    ERRORS:
      - API_DCX_NETWORK_NICKNAME_REQUIRED:
          suggested_action: Choose a nickname in Settings before posting.
          common_causes:
            - account has no public_handle
          recovery_steps:
            - Open Settings and save a nickname.
          retry_safe: true
      - API_DCX_NETWORK_FEED_POST_INVALID:
          suggested_action: Keep the post between 1 and 500 characters.
          common_causes:
            - empty post
            - overly long post
          recovery_steps:
            - Edit the post and retry.
          retry_safe: true
      - API_DCX_NETWORK_CONTENT_PROHIBITED:
          suggested_action: Rewrite the post without prohibited content.
          common_causes:
            - content policy violation
          recovery_steps:
            - Remove prohibited material and retry.
          retry_safe: true

    CODE:
    """
    normalized_post_text = post_text.strip() if isinstance(post_text, str) else ""
    if len(normalized_post_text) < 1 or len(normalized_post_text) > 500:
        raise RuntimeError("API_DCX_NETWORK_FEED_POST_INVALID")

    normalized_language_code = normalize_dcx_network_language_code(language_code)

    policy_check = read_dcx_network_policy_check(
        content_kind="network_feed_post",
        raw_text_content=normalized_post_text,
        authenticated_user_id=authenticated_user_id,
    )
    if policy_check.get("moderation_status") == "prohibited":
        raise RuntimeError("API_DCX_NETWORK_CONTENT_PROHIBITED")

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                author_row = _read_network_user_by_id(cursor, authenticated_user_id)
                if author_row is None or not _read_public_handle(author_row[2]):
                    raise RuntimeError("API_DCX_NETWORK_NICKNAME_REQUIRED")

                cursor.execute(
                    """
                    INSERT INTO public.stephen_dcx_network_feed_posts (
                        author_user_id,
                        post_text,
                        language_code,
                        moderation_metadata_json,
                        post_metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        authenticated_user_id,
                        normalized_post_text,
                        normalized_language_code,
                        Json(policy_check),
                        Json({"translation_status": "not_started"}),
                    ),
                )
                post_id = cursor.fetchone()[0]
                return _read_network_feed_post_by_id(
                    cursor=cursor,
                    post_id=post_id,
                    viewer_user_id=authenticated_user_id,
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NETWORK_FEED_POST_CREATE_FAILED") from exc


def append_authenticated_dcx_network_feed_reply(
    authenticated_user_id: int,
    feed_post_id: int,
    reply_text: str,
    language_code: str = "en",
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id is one signed-in DCX user id with a public nickname.
        - feed_post_id identifies one active network post.
        - reply_text is 1-500 characters after trimming.
      postconditions:
        - Stores one one-level reply under the target post.
        - Blocks prohibited content before persistence.
        - Returns the refreshed post payload with replies.
      side_effects:
        - writes one row in `stephen_dcx_network_feed_replies`
        - updates the parent post timestamp
        - may call Gemini for content policy
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - parent post row update timestamp lock
      contention_strategy: replies append independently; parent timestamp converges on latest write

    NARRATIVE:
      WHY this exists:
        - One-level replies keep network discussion simple and readable while still allowing public
          trust-building interaction around posts.
      WHEN TO USE it:
        - Use it from the feed post reply box.
      WHEN NOT TO USE it:
        - Do not use it for nested comment trees.
      WHAT CAN GO WRONG:
        - The post can be gone or not active.
        - The reply can be empty, too long, or prohibited.
      WHAT COMES NEXT:
        - Add notifications and translations.

    TESTS:
      - No dedicated network tests exist yet; route smoke and TypeScript compile cover this first slice.

    ERRORS:
      - API_DCX_NETWORK_FEED_POST_NOT_FOUND:
          suggested_action: Refresh the feed and retry with a current post.
          retry_safe: true
      - API_DCX_NETWORK_FEED_REPLY_INVALID:
          suggested_action: Keep the reply between 1 and 500 characters.
          retry_safe: true
      - API_DCX_NETWORK_CONTENT_PROHIBITED:
          suggested_action: Rewrite the reply without prohibited content.
          retry_safe: true

    CODE:
    """
    if not isinstance(feed_post_id, int) or feed_post_id <= 0:
        raise RuntimeError("API_DCX_NETWORK_FEED_POST_NOT_FOUND")

    normalized_reply_text = reply_text.strip() if isinstance(reply_text, str) else ""
    if len(normalized_reply_text) < 1 or len(normalized_reply_text) > 500:
        raise RuntimeError("API_DCX_NETWORK_FEED_REPLY_INVALID")

    normalized_language_code = normalize_dcx_network_language_code(language_code)
    policy_check = read_dcx_network_policy_check(
        content_kind="network_feed_reply",
        raw_text_content=normalized_reply_text,
        authenticated_user_id=authenticated_user_id,
    )
    if policy_check.get("moderation_status") == "prohibited":
        raise RuntimeError("API_DCX_NETWORK_CONTENT_PROHIBITED")

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                author_row = _read_network_user_by_id(cursor, authenticated_user_id)
                if author_row is None or not _read_public_handle(author_row[2]):
                    raise RuntimeError("API_DCX_NETWORK_NICKNAME_REQUIRED")

                cursor.execute(
                    """
                    SELECT id
                    FROM public.stephen_dcx_network_feed_posts
                    WHERE id = %s
                      AND post_status = 'active'
                    FOR UPDATE
                    """,
                    (feed_post_id,),
                )
                if cursor.fetchone() is None:
                    raise RuntimeError("API_DCX_NETWORK_FEED_POST_NOT_FOUND")

                cursor.execute(
                    """
                    INSERT INTO public.stephen_dcx_network_feed_replies (
                        feed_post_id,
                        author_user_id,
                        reply_text,
                        language_code,
                        moderation_metadata_json,
                        reply_metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        feed_post_id,
                        authenticated_user_id,
                        normalized_reply_text,
                        normalized_language_code,
                        Json(policy_check),
                        Json({"translation_status": "not_started"}),
                    ),
                )
                cursor.execute(
                    """
                    UPDATE public.stephen_dcx_network_feed_posts
                    SET updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
                    WHERE id = %s
                    """,
                    (feed_post_id,),
                )
                return _read_network_feed_post_by_id(
                    cursor=cursor,
                    post_id=feed_post_id,
                    viewer_user_id=authenticated_user_id,
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NETWORK_FEED_REPLY_CREATE_FAILED") from exc


def read_authenticated_dcx_network_dm_threads(
    authenticated_user_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id is one signed-in DCX user id.
      postconditions:
        - Returns the user's DM thread list with the other participant and latest message.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - DMs give traders a weak, low-pressure first-contact lane distinct from structured Trade Chats.
      WHEN TO USE it:
        - Use it for `/network/dms`.
      WHEN NOT TO USE it:
        - Do not use it for trade negotiation records that need structured accountability.
      WHAT CAN GO WRONG:
        - The network migration may not be applied.
      WHAT COMES NEXT:
        - Add unread counts, notification preferences, and block/mute tools.

    TESTS:
      - No dedicated network tests exist yet; route smoke and TypeScript compile cover this first slice.

    ERRORS:
      - API_DCX_NETWORK_DMS_READ_FAILED:
          suggested_action: Retry after confirming database health.
          retry_safe: true

    CODE:
    """
    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        thread.id,
                        thread.thread_status,
                        thread.updated_at_ts_ms,
                        other_user.id,
                        other_user.public_display_name,
                        other_user.public_handle,
                        other_user.public_identity_mode,
                        COALESCE(other_user.network_profile_image_url, ''),
                        latest_message.id,
                        latest_message.sender_user_id,
                        latest_message.raw_message_text,
                        latest_message.canonical_message_text,
                        latest_message.language_code,
                        latest_message.translations_json,
                        latest_message.created_at_ts_ms
                    FROM public.stephen_dcx_network_dm_threads thread
                    JOIN public.stephen_dcx_users other_user
                      ON other_user.id = CASE
                          WHEN thread.participant_user_id_1 = %s THEN thread.participant_user_id_2
                          ELSE thread.participant_user_id_1
                      END
                    LEFT JOIN LATERAL (
                        SELECT
                            id,
                            sender_user_id,
                            raw_message_text,
                            canonical_message_text,
                            language_code,
                            translations_json,
                            created_at_ts_ms
                        FROM public.stephen_dcx_network_dm_messages
                        WHERE dm_thread_id = thread.id
                          AND message_status = 'active'
                        ORDER BY created_at_ts_ms DESC, id DESC
                        LIMIT 1
                    ) latest_message
                      ON TRUE
                    WHERE %s IN (thread.participant_user_id_1, thread.participant_user_id_2)
                      AND thread.thread_status IN ('open', 'archived')
                    ORDER BY thread.updated_at_ts_ms DESC, thread.id DESC
                    LIMIT 100
                    """,
                    (
                        authenticated_user_id,
                        authenticated_user_id,
                    ),
                )
                thread_rows = cursor.fetchall()
                return {
                    "dm_threads": [
                        _read_network_dm_thread_catalog_payload(thread_row, authenticated_user_id)
                        for thread_row in thread_rows
                    ]
                }
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NETWORK_DMS_READ_FAILED") from exc


def start_authenticated_dcx_network_dm_thread(
    authenticated_user_id: int,
    network_nickname: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id is one signed-in DCX user id.
        - network_nickname identifies another DCX profile.
        - The target user's DM preference allows this sender.
      postconditions:
        - Opens or reopens one two-person DM thread.
        - Returns the thread detail.
      side_effects:
        - writes or updates `stephen_dcx_network_dm_threads`
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: network_dm_thread:{min_user_id}:{max_user_id}
      locks:
        - unique participant pair index on `stephen_dcx_network_dm_threads`
      contention_strategy: unique upsert lets repeated starts converge on one thread

    NARRATIVE:
      WHY this exists:
        - Profiles need a clear low-pressure “message” action separate from Trade Chats.
      WHEN TO USE it:
        - Use it from a profile DM button or a future recipient search.
      WHEN NOT TO USE it:
        - Do not use it if the recipient has disabled DMs or accepts only followed contacts.
      WHAT CAN GO WRONG:
        - The recipient may not exist or may not accept DMs from this user.
      WHAT COMES NEXT:
        - Add user search and block/mute mechanics.

    TESTS:
      - No dedicated network tests exist yet; route smoke and TypeScript compile cover this first slice.

    ERRORS:
      - API_DCX_NETWORK_DM_NOT_ALLOWED:
          suggested_action: The recipient does not currently accept DMs from this account.
          retry_safe: true

    CODE:
    """
    normalized_nickname = normalize_dcx_network_nickname(network_nickname)
    if normalized_nickname is None:
        raise RuntimeError("API_DCX_NETWORK_PROFILE_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                target_row = _read_network_user_profile_row(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    network_nickname=normalized_nickname,
                )
                if target_row is None:
                    raise RuntimeError("API_DCX_NETWORK_PROFILE_NOT_FOUND")
                target_user_id = int(target_row[0])
                if target_user_id == authenticated_user_id:
                    raise RuntimeError("API_DCX_NETWORK_DM_NOT_ALLOWED")
                if not _read_can_authenticated_user_dm_target_from_profile_row(target_row):
                    raise RuntimeError("API_DCX_NETWORK_DM_NOT_ALLOWED")

                first_user_id, second_user_id = sorted([authenticated_user_id, target_user_id])
                cursor.execute(
                    """
                    INSERT INTO public.stephen_dcx_network_dm_threads (
                        participant_user_id_1,
                        participant_user_id_2,
                        thread_status
                    )
                    VALUES (%s, %s, 'open')
                    ON CONFLICT (participant_user_id_1, participant_user_id_2) DO UPDATE
                    SET
                        thread_status = CASE
                            WHEN public.stephen_dcx_network_dm_threads.thread_status = 'blocked'
                            THEN 'blocked'
                            ELSE 'open'
                        END,
                        updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
                    RETURNING id, thread_status
                    """,
                    (
                        first_user_id,
                        second_user_id,
                    ),
                )
                thread_id, thread_status = cursor.fetchone()
                if thread_status == "blocked":
                    raise RuntimeError("API_DCX_NETWORK_DM_NOT_ALLOWED")
                return _read_network_dm_thread_detail_payload(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    dm_thread_id=thread_id,
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NETWORK_DM_START_FAILED") from exc


def read_authenticated_dcx_network_dm_thread(
    authenticated_user_id: int,
    dm_thread_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id is one signed-in participant in the requested thread.
      postconditions:
        - Returns the thread detail with messages visible to the authenticated user.
        - Returns null when the user is not a participant or the thread does not exist.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The DM detail page needs one read contract that never leaks conversations to non-participants.
      WHEN TO USE it:
        - Use it for `/network/dms/{id}`.
      WHEN NOT TO USE it:
        - Do not use it for Trade Chats.
      WHAT CAN GO WRONG:
        - The thread id can be stale.
      WHAT COMES NEXT:
        - Add read receipts and unread counters later.

    TESTS:
      - No dedicated network tests exist yet; route smoke and TypeScript compile cover this first slice.

    ERRORS:
      - API_DCX_NETWORK_DM_READ_FAILED:
          suggested_action: Retry after confirming database health.
          retry_safe: true

    CODE:
    """
    if not isinstance(dm_thread_id, int) or dm_thread_id <= 0:
        return None

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                return _read_network_dm_thread_detail_payload(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    dm_thread_id=dm_thread_id,
                )
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NETWORK_DM_READ_FAILED") from exc


def append_authenticated_dcx_network_dm_message(
    authenticated_user_id: int,
    dm_thread_id: int,
    message_text: str,
    language_code: str = "en",
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - authenticated_user_id is one signed-in participant in the thread.
        - message_text is 1-2000 characters after trimming.
      postconditions:
        - Stores one DM message.
        - Blocks prohibited content before persistence.
        - Best-effort translates for the recipient's primary language when useful.
        - Returns refreshed thread detail.
      side_effects:
        - writes one row in `stephen_dcx_network_dm_messages`
        - updates `stephen_dcx_network_dm_threads.updated_at_ts_ms`
        - may call Gemini for moderation and translation
      idempotent: false
      retry_safe: false
      async: false
      idempotency_key: none
      locks:
        - target thread row lock while appending the message
      contention_strategy: messages append independently; thread timestamp converges on newest write

    NARRATIVE:
      WHY this exists:
        - DMs need to feel natural while preserving the core DCX promise that cross-language
          traders can begin trust-building conversations.
      WHEN TO USE it:
        - Use it from the DM composer.
      WHEN NOT TO USE it:
        - Do not use it for structured Trade Chat negotiations.
      WHAT CAN GO WRONG:
        - The sender may not be a participant.
        - The message can be empty, too long, or prohibited.
        - Translation can fail; the original message is still saved.
      WHAT COMES NEXT:
        - Add delivery notifications and translation retry jobs.

    TESTS:
      - No dedicated network tests exist yet; route smoke and TypeScript compile cover this first slice.

    ERRORS:
      - API_DCX_NETWORK_DM_NOT_FOUND:
          suggested_action: Refresh DMs and retry with a current thread.
          retry_safe: true
      - API_DCX_NETWORK_DM_MESSAGE_INVALID:
          suggested_action: Keep the message between 1 and 2000 characters.
          retry_safe: true
      - API_DCX_NETWORK_CONTENT_PROHIBITED:
          suggested_action: Rewrite the message without prohibited content.
          retry_safe: true

    CODE:
    """
    if not isinstance(dm_thread_id, int) or dm_thread_id <= 0:
        raise RuntimeError("API_DCX_NETWORK_DM_NOT_FOUND")

    normalized_message_text = message_text.strip() if isinstance(message_text, str) else ""
    if len(normalized_message_text) < 1 or len(normalized_message_text) > 2000:
        raise RuntimeError("API_DCX_NETWORK_DM_MESSAGE_INVALID")

    normalized_language_code = normalize_dcx_network_language_code(language_code)
    policy_check = read_dcx_network_policy_check(
        content_kind="network_dm_message",
        raw_text_content=normalized_message_text,
        authenticated_user_id=authenticated_user_id,
    )
    if policy_check.get("moderation_status") == "prohibited":
        raise RuntimeError("API_DCX_NETWORK_CONTENT_PROHIBITED")

    connect = connect_to_database or psycopg2.connect
    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                thread_row = _read_network_dm_thread_participants_for_update(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    dm_thread_id=dm_thread_id,
                )
                if thread_row is None:
                    raise RuntimeError("API_DCX_NETWORK_DM_NOT_FOUND")

                recipient_user_id = (
                    thread_row[1]
                    if int(thread_row[0]) == authenticated_user_id
                    else thread_row[0]
                )
                translations_json = _build_network_dm_translations_json(
                    cursor=cursor,
                    recipient_user_id=int(recipient_user_id),
                    raw_message_text=normalized_message_text,
                    source_language_code=normalized_language_code,
                )

                cursor.execute(
                    """
                    INSERT INTO public.stephen_dcx_network_dm_messages (
                        dm_thread_id,
                        sender_user_id,
                        raw_message_text,
                        canonical_message_text,
                        language_code,
                        translations_json,
                        moderation_metadata_json,
                        message_metadata_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        dm_thread_id,
                        authenticated_user_id,
                        normalized_message_text,
                        normalized_message_text,
                        normalized_language_code,
                        Json(translations_json),
                        Json(policy_check),
                        Json({"translation_status": translations_json.get("translation_status", "not_needed")}),
                    ),
                )
                cursor.execute(
                    """
                    UPDATE public.stephen_dcx_network_dm_threads
                    SET updated_at_ts_ms = ((EXTRACT(EPOCH FROM clock_timestamp()) * 1000::numeric)::bigint)
                    WHERE id = %s
                    """,
                    (dm_thread_id,),
                )
                return _read_network_dm_thread_detail_payload(
                    cursor=cursor,
                    authenticated_user_id=authenticated_user_id,
                    dm_thread_id=dm_thread_id,
                )
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_NETWORK_DM_MESSAGE_CREATE_FAILED") from exc


def normalize_dcx_network_nickname(value: str | None) -> str | None:
    normalized_value = value.strip().lower().removeprefix("@") if isinstance(value, str) else ""
    if NETWORK_HANDLE_PATTERN.fullmatch(normalized_value) is None:
        return None
    if normalized_value in NETWORK_RESERVED_HANDLES:
        return None
    return normalized_value


def normalize_dcx_network_language_code(value: str | None) -> str:
    normalized_value = value.strip().lower() if isinstance(value, str) else "en"
    if NETWORK_TEXT_LANGUAGE_PATTERN.fullmatch(normalized_value) is None:
        return "en"
    return normalized_value


def read_dcx_network_policy_check(
    content_kind: str,
    raw_text_content: str,
    authenticated_user_id: int,
) -> dict:
    try:
        return generate_dcx_gemini_user_content_policy_check(
            content_input={
                "content_id": 0,
                "content_kind": content_kind,
                "surface": "dcx_app_network",
                "channel_type": "app",
                "provider_type": "dcx_app",
                "message_format": "text",
                "message_subject": f"user:{authenticated_user_id}",
                "raw_text_content": raw_text_content,
            },
        )
    except RuntimeError:
        return {
            "provider_name": "google_gemini",
            "model_name": "",
            "prompt_version": "dcx_user_content_policy_check_2026_06_25_v1",
            "analysis_mode": "fallback_policy_unavailable",
            "policy_check_status": "skipped",
            "moderation_status": "not_reviewed",
            "moderation_reason_summary": "",
            "matched_prohibited_categories": [],
            "user_facing_message": "",
            "should_redact_original": False,
            "usage_metadata": {},
        }


def _read_network_user_profile_row(cursor, authenticated_user_id: int, network_nickname: str):
    cursor.execute(
        """
        SELECT
            target_user.id,
            target_user.public_display_name,
            target_user.public_handle,
            target_user.public_identity_mode,
            COALESCE(target_user.network_profile_image_url, ''),
            COALESCE(target_user.network_dm_acceptance_mode, 'everyone'),
            target_user.created_at_ts_ms,
            (
                SELECT COUNT(*)
                FROM public.stephen_dcx_network_follows follower_count
                WHERE follower_count.followed_user_id = target_user.id
                  AND follower_count.follow_status = 'active'
            ) AS follower_count,
            (
                SELECT COUNT(*)
                FROM public.stephen_dcx_network_follows following_count
                WHERE following_count.follower_user_id = target_user.id
                  AND following_count.follow_status = 'active'
            ) AS following_count,
            EXISTS (
                SELECT 1
                FROM public.stephen_dcx_network_follows viewer_follow
                WHERE viewer_follow.follower_user_id = %s
                  AND viewer_follow.followed_user_id = target_user.id
                  AND viewer_follow.follow_status = 'active'
            ) AS is_followed_by_authenticated_user,
            EXISTS (
                SELECT 1
                FROM public.stephen_dcx_network_follows target_follow
                WHERE target_follow.follower_user_id = target_user.id
                  AND target_follow.followed_user_id = %s
                  AND target_follow.follow_status = 'active'
            ) AS is_following_authenticated_user
        FROM public.stephen_dcx_users target_user
        WHERE lower(target_user.public_handle) = %s
          AND btrim(target_user.public_handle) <> ''
        LIMIT 1
        """,
        (
            authenticated_user_id,
            authenticated_user_id,
            network_nickname,
        ),
    )
    return cursor.fetchone()


def _read_network_user_by_id(cursor, user_id: int):
    cursor.execute(
        """
        SELECT
            id,
            public_display_name,
            public_handle,
            public_identity_mode,
            COALESCE(network_profile_image_url, ''),
            COALESCE(network_dm_acceptance_mode, 'everyone')
        FROM public.stephen_dcx_users
        WHERE id = %s
        LIMIT 1
        """,
        (user_id,),
    )
    return cursor.fetchone()


def _read_network_profile_payload_from_row(profile_row: tuple) -> dict:
    profile_payload = {
        "user_id": profile_row[0],
        "public_display_name": profile_row[1] or "",
        "public_handle": _read_public_handle(profile_row[2]),
        "public_identity_mode": profile_row[3] or "display_name",
        "profile_image_url": profile_row[4] or "",
        "dm_acceptance_mode": profile_row[5] or "everyone",
        "created_at_ts_ms": profile_row[6],
        "follower_count": int(profile_row[7] or 0),
        "following_count": int(profile_row[8] or 0),
        "is_followed_by_authenticated_user": profile_row[9] is True,
        "is_following_authenticated_user": profile_row[10] is True,
    }
    profile_payload["public_identity_label"] = _read_network_public_identity_label(
        user_id=profile_payload["user_id"],
        public_display_name=profile_payload["public_display_name"],
        public_handle=profile_payload["public_handle"],
        public_identity_mode=profile_payload["public_identity_mode"],
    )
    profile_payload["can_dm"] = _read_can_authenticated_user_dm_target_from_profile_row(profile_row)
    profile_payload["is_self"] = False
    return profile_payload


def _read_can_authenticated_user_dm_target_from_profile_row(profile_row: tuple) -> bool:
    dm_acceptance_mode = str(profile_row[5] or "everyone").strip().lower()
    if dm_acceptance_mode == "none":
        return False
    if dm_acceptance_mode == "following":
        return profile_row[10] is True
    return True


def _read_network_badges_for_user(cursor, user_id: int) -> dict:
    cursor.execute(
        """
        SELECT
            language.id,
            language.language_code,
            language.language_name_en,
            language.language_name_native,
            language.is_rtl
        FROM public.stephen_dcx_user_languages user_language
        JOIN public.stephen_dcx_languages language
          ON language.id = user_language.language_id
        WHERE user_language.user_id = %s
          AND language.is_active = TRUE
        ORDER BY user_language.sort_order ASC, language.language_code ASC
        """,
        (user_id,),
    )
    language_rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            timezone.id,
            timezone.iana_name,
            timezone.display_label,
            timezone.region_label,
            country.country_code_alpha2,
            country.default_display_name,
            country.flag_asset_key
        FROM public.stephen_dcx_user_timezones user_timezone
        JOIN public.stephen_dcx_timezones timezone
          ON timezone.id = user_timezone.timezone_id
        LEFT JOIN public.stephen_dcx_countries country
          ON country.id = timezone.country_id
        WHERE user_timezone.user_id = %s
          AND timezone.is_active = TRUE
        ORDER BY user_timezone.sort_order ASC, timezone.display_label ASC
        """,
        (user_id,),
    )
    timezone_rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            country.id,
            country.country_code_alpha2,
            country.default_display_name,
            country.flag_asset_key
        FROM public.stephen_dcx_user_countries user_country
        JOIN public.stephen_dcx_countries country
          ON country.id = user_country.country_id
        WHERE user_country.user_id = %s
          AND country.is_active = TRUE
        ORDER BY user_country.sort_order ASC, country.default_display_name ASC
        """,
        (user_id,),
    )
    country_rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            user_material.material_key,
            material.display_label,
            user_material.sort_order
        FROM public.stephen_dcx_user_trade_interest_materials user_material
        JOIN public.stephen_dcx_trade_interest_material_options material
          ON material.material_key = user_material.material_key
        WHERE user_material.user_id = %s
          AND material.is_active = TRUE
        ORDER BY user_material.sort_order ASC, material.display_label ASC
        """,
        (user_id,),
    )
    material_rows = cursor.fetchall()

    return {
        "languages": [
            {
                "id": row[0],
                "language_code": row[1],
                "language_name_en": row[2],
                "language_name_native": row[3],
                "is_rtl": row[4],
            }
            for row in language_rows
        ],
        "timezones": [
            {
                "id": row[0],
                "iana_name": row[1],
                "display_label": row[2],
                "region_label": row[3],
                "country_code_alpha2": row[4],
                "country_display_name": row[5],
                "flag_asset_key": row[6],
            }
            for row in timezone_rows
        ],
        "countries": [
            {
                "id": row[0],
                "country_code_alpha2": row[1],
                "default_display_name": row[2],
                "flag_asset_key": row[3],
            }
            for row in country_rows
        ],
        "commodities": [
            {
                "material_key": row[0],
                "display_label": row[1],
                "sort_order": row[2],
            }
            for row in material_rows
        ],
    }


def _build_network_feed_posts_query(feed_scope: str) -> str:
    following_clause = ""
    if feed_scope == "following":
        following_clause = """
          AND (
              post.author_user_id = viewer.user_id
              OR EXISTS (
                  SELECT 1
                  FROM public.stephen_dcx_network_follows follow
                  WHERE follow.follower_user_id = viewer.user_id
                    AND follow.followed_user_id = post.author_user_id
                    AND follow.follow_status = 'active'
              )
          )
        """
        return _NETWORK_FEED_POST_SELECT_SQL.replace("/* following_clause */", following_clause)

    return _NETWORK_FEED_POST_SELECT_SQL.replace(
        "/* following_clause */",
        "          AND TRUE",
    )


_NETWORK_FEED_POST_SELECT_SQL = """
WITH viewer AS (
    SELECT %s::bigint AS user_id
)
SELECT
    post.id,
    post.author_user_id,
    post.post_text,
    post.language_code,
    post.translations_json,
    post.created_at_ts_ms,
    post.updated_at_ts_ms,
    author.public_display_name,
    author.public_handle,
    author.public_identity_mode,
    COALESCE(author.network_profile_image_url, ''),
    (
        SELECT COUNT(*)
        FROM public.stephen_dcx_network_feed_replies reply_count
        WHERE reply_count.feed_post_id = post.id
          AND reply_count.reply_status = 'active'
    ) AS reply_count,
    EXISTS (
        SELECT 1
        FROM public.stephen_dcx_network_follows follow_state
        WHERE follow_state.follower_user_id = viewer.user_id
          AND follow_state.followed_user_id = post.author_user_id
          AND follow_state.follow_status = 'active'
    ) AS viewer_follows_author
FROM public.stephen_dcx_network_feed_posts post
Cross JOIN viewer
JOIN public.stephen_dcx_users author
  ON author.id = post.author_user_id
WHERE post.post_status = 'active'
  AND post.visibility_status = 'app_public'
/* following_clause */
ORDER BY post.created_at_ts_ms DESC, post.id DESC
LIMIT 100
"""


def _read_network_recent_posts_for_profile(cursor, authenticated_user_id: int, profile_user_id: int) -> list[dict]:
    cursor.execute(
        """
        SELECT
            post.id,
            post.author_user_id,
            post.post_text,
            post.language_code,
            post.translations_json,
            post.created_at_ts_ms,
            post.updated_at_ts_ms,
            author.public_display_name,
            author.public_handle,
            author.public_identity_mode,
            COALESCE(author.network_profile_image_url, ''),
            (
                SELECT COUNT(*)
                FROM public.stephen_dcx_network_feed_replies reply_count
                WHERE reply_count.feed_post_id = post.id
                  AND reply_count.reply_status = 'active'
            ) AS reply_count,
            EXISTS (
                SELECT 1
                FROM public.stephen_dcx_network_follows follow_state
                WHERE follow_state.follower_user_id = %s
                  AND follow_state.followed_user_id = post.author_user_id
                  AND follow_state.follow_status = 'active'
            ) AS viewer_follows_author
        FROM public.stephen_dcx_network_feed_posts post
        JOIN public.stephen_dcx_users author
          ON author.id = post.author_user_id
        WHERE post.author_user_id = %s
          AND post.post_status = 'active'
          AND post.visibility_status = 'app_public'
        ORDER BY post.created_at_ts_ms DESC, post.id DESC
        LIMIT 10
        """,
        (
            authenticated_user_id,
            profile_user_id,
        ),
    )
    post_rows = cursor.fetchall()
    post_ids = [row[0] for row in post_rows]
    reply_rows_by_post_id = _read_network_reply_rows_by_post_id(cursor, post_ids)
    return [
        _read_network_feed_post_payload(
            post_row=post_row,
            reply_rows=reply_rows_by_post_id.get(post_row[0], []),
            viewer_user_id=authenticated_user_id,
        )
        for post_row in post_rows
    ]


def _read_network_reply_rows_by_post_id(cursor, post_ids: list[int]) -> dict[int, list[tuple]]:
    if not post_ids:
        return {}

    cursor.execute(
        """
        SELECT
            reply.feed_post_id,
            reply.id,
            reply.author_user_id,
            reply.reply_text,
            reply.language_code,
            reply.translations_json,
            reply.created_at_ts_ms,
            author.public_display_name,
            author.public_handle,
            author.public_identity_mode,
            COALESCE(author.network_profile_image_url, '')
        FROM public.stephen_dcx_network_feed_replies reply
        JOIN public.stephen_dcx_users author
          ON author.id = reply.author_user_id
        WHERE reply.feed_post_id = ANY(%s)
          AND reply.reply_status = 'active'
        ORDER BY reply.created_at_ts_ms ASC, reply.id ASC
        """,
        (post_ids,),
    )
    rows_by_post_id: dict[int, list[tuple]] = {}
    for row in cursor.fetchall():
        rows_by_post_id.setdefault(row[0], []).append(row)
    return rows_by_post_id


def _read_network_feed_post_by_id(cursor, post_id: int, viewer_user_id: int) -> dict:
    cursor.execute(
        """
        SELECT
            post.id,
            post.author_user_id,
            post.post_text,
            post.language_code,
            post.translations_json,
            post.created_at_ts_ms,
            post.updated_at_ts_ms,
            author.public_display_name,
            author.public_handle,
            author.public_identity_mode,
            COALESCE(author.network_profile_image_url, ''),
            (
                SELECT COUNT(*)
                FROM public.stephen_dcx_network_feed_replies reply_count
                WHERE reply_count.feed_post_id = post.id
                  AND reply_count.reply_status = 'active'
            ) AS reply_count,
            EXISTS (
                SELECT 1
                FROM public.stephen_dcx_network_follows follow_state
                WHERE follow_state.follower_user_id = %s
                  AND follow_state.followed_user_id = post.author_user_id
                  AND follow_state.follow_status = 'active'
            ) AS viewer_follows_author
        FROM public.stephen_dcx_network_feed_posts post
        JOIN public.stephen_dcx_users author
          ON author.id = post.author_user_id
        WHERE post.id = %s
        LIMIT 1
        """,
        (
            viewer_user_id,
            post_id,
        ),
    )
    post_row = cursor.fetchone()
    if post_row is None:
        raise RuntimeError("API_DCX_NETWORK_FEED_POST_NOT_FOUND")
    reply_rows = _read_network_reply_rows_by_post_id(cursor, [post_id]).get(post_id, [])
    return _read_network_feed_post_payload(post_row, reply_rows, viewer_user_id)


def _read_network_feed_post_payload(post_row: tuple, reply_rows: list[tuple], viewer_user_id: int) -> dict:
    return {
        "feed_post_id": post_row[0],
        "author": _read_network_author_payload(
            user_id=post_row[1],
            public_display_name=post_row[7],
            public_handle=post_row[8],
            public_identity_mode=post_row[9],
            profile_image_url=post_row[10],
        ),
        "post_text": post_row[2],
        "language_code": post_row[3],
        "translations_json": post_row[4] if isinstance(post_row[4], dict) else {},
        "created_at_ts_ms": post_row[5],
        "updated_at_ts_ms": post_row[6],
        "reply_count": int(post_row[11] or 0),
        "viewer_follows_author": post_row[12] is True or int(post_row[1]) == viewer_user_id,
        "is_owned_by_authenticated_user": int(post_row[1]) == viewer_user_id,
        "replies": [
            _read_network_feed_reply_payload(reply_row, viewer_user_id)
            for reply_row in reply_rows
        ],
    }


def _read_network_feed_reply_payload(reply_row: tuple, viewer_user_id: int) -> dict:
    return {
        "feed_reply_id": reply_row[1],
        "feed_post_id": reply_row[0],
        "author": _read_network_author_payload(
            user_id=reply_row[2],
            public_display_name=reply_row[7],
            public_handle=reply_row[8],
            public_identity_mode=reply_row[9],
            profile_image_url=reply_row[10],
        ),
        "reply_text": reply_row[3],
        "language_code": reply_row[4],
        "translations_json": reply_row[5] if isinstance(reply_row[5], dict) else {},
        "created_at_ts_ms": reply_row[6],
        "is_owned_by_authenticated_user": int(reply_row[2]) == viewer_user_id,
    }


def _read_network_dm_thread_participants_for_update(cursor, authenticated_user_id: int, dm_thread_id: int):
    cursor.execute(
        """
        SELECT
            participant_user_id_1,
            participant_user_id_2
        FROM public.stephen_dcx_network_dm_threads
        WHERE id = %s
          AND thread_status = 'open'
          AND %s IN (participant_user_id_1, participant_user_id_2)
        FOR UPDATE
        """,
        (
            dm_thread_id,
            authenticated_user_id,
        ),
    )
    return cursor.fetchone()


def _read_network_dm_thread_detail_payload(cursor, authenticated_user_id: int, dm_thread_id: int) -> dict | None:
    cursor.execute(
        """
        SELECT
            thread.id,
            thread.thread_status,
            thread.created_at_ts_ms,
            thread.updated_at_ts_ms,
            other_user.id,
            other_user.public_display_name,
            other_user.public_handle,
            other_user.public_identity_mode,
            COALESCE(other_user.network_profile_image_url, '')
        FROM public.stephen_dcx_network_dm_threads thread
        JOIN public.stephen_dcx_users other_user
          ON other_user.id = CASE
              WHEN thread.participant_user_id_1 = %s THEN thread.participant_user_id_2
              ELSE thread.participant_user_id_1
          END
        WHERE thread.id = %s
          AND %s IN (thread.participant_user_id_1, thread.participant_user_id_2)
          AND thread.thread_status IN ('open', 'archived')
        LIMIT 1
        """,
        (
            authenticated_user_id,
            dm_thread_id,
            authenticated_user_id,
        ),
    )
    thread_row = cursor.fetchone()
    if thread_row is None:
        return None

    cursor.execute(
        """
        SELECT
            id,
            sender_user_id,
            raw_message_text,
            canonical_message_text,
            language_code,
            translations_json,
            created_at_ts_ms
        FROM public.stephen_dcx_network_dm_messages
        WHERE dm_thread_id = %s
          AND message_status = 'active'
        ORDER BY created_at_ts_ms ASC, id ASC
        LIMIT 250
        """,
        (dm_thread_id,),
    )
    message_rows = cursor.fetchall()
    return {
        "dm_thread_id": thread_row[0],
        "thread_status": thread_row[1],
        "created_at_ts_ms": thread_row[2],
        "updated_at_ts_ms": thread_row[3],
        "other_participant": _read_network_author_payload(
            user_id=thread_row[4],
            public_display_name=thread_row[5],
            public_handle=thread_row[6],
            public_identity_mode=thread_row[7],
            profile_image_url=thread_row[8],
        ),
        "messages": [
            _read_network_dm_message_payload(message_row, authenticated_user_id)
            for message_row in message_rows
        ],
    }


def _read_network_dm_thread_catalog_payload(thread_row: tuple, viewer_user_id: int) -> dict:
    translations_json = thread_row[13] if isinstance(thread_row[13], dict) else {}
    return {
        "dm_thread_id": thread_row[0],
        "thread_status": thread_row[1],
        "updated_at_ts_ms": thread_row[2],
        "other_participant": _read_network_author_payload(
            user_id=thread_row[3],
            public_display_name=thread_row[4],
            public_handle=thread_row[5],
            public_identity_mode=thread_row[6],
            profile_image_url=thread_row[7],
        ),
        "latest_message": (
            {
                "dm_message_id": thread_row[8],
                "sender_user_id": thread_row[9],
                "message_text": _read_translated_message_for_viewer(
                    raw_message_text=thread_row[10] or thread_row[11] or "",
                    translations_json=translations_json,
                    viewer_user_id=viewer_user_id,
                ),
                "raw_message_text": thread_row[10] or "",
                "language_code": thread_row[12] or "en",
                "created_at_ts_ms": thread_row[14],
                "is_owned_by_authenticated_user": thread_row[9] == viewer_user_id,
            }
            if thread_row[8] is not None
            else None
        ),
    }


def _read_network_dm_message_payload(message_row: tuple, viewer_user_id: int) -> dict:
    translations_json = message_row[5] if isinstance(message_row[5], dict) else {}
    return {
        "dm_message_id": message_row[0],
        "sender_user_id": message_row[1],
        "message_text": _read_translated_message_for_viewer(
            raw_message_text=message_row[2] or message_row[3] or "",
            translations_json=translations_json,
            viewer_user_id=viewer_user_id,
        ),
        "raw_message_text": message_row[2] or "",
        "canonical_message_text": message_row[3] or "",
        "language_code": message_row[4] or "en",
        "translations_json": translations_json,
        "created_at_ts_ms": message_row[6],
        "is_owned_by_authenticated_user": int(message_row[1]) == viewer_user_id,
    }


def _read_translated_message_for_viewer(raw_message_text: str, translations_json: dict, viewer_user_id: int) -> str:
    viewer_translation = translations_json.get(str(viewer_user_id)) if isinstance(translations_json, dict) else None
    if isinstance(viewer_translation, dict):
        translated_text = str(viewer_translation.get("message_text") or "").strip()
        if translated_text:
            return translated_text
    return raw_message_text


def _build_network_dm_translations_json(
    cursor,
    recipient_user_id: int,
    raw_message_text: str,
    source_language_code: str,
) -> dict:
    recipient_languages = _read_selected_language_codes_for_user(cursor, recipient_user_id)
    if not recipient_languages:
        recipient_languages = ["en"]
    if source_language_code in recipient_languages:
        return {"translation_status": "not_needed"}

    target_language_code = recipient_languages[0]
    if target_language_code == source_language_code:
        return {"translation_status": "not_needed"}

    try:
        translation_payload = translate_dcx_gemini_trade_thread_message(
            message_text=raw_message_text,
            source_language_code=source_language_code,
            target_language_code=target_language_code,
        )
        return {
            "translation_status": "completed",
            str(recipient_user_id): {
                "language_code": target_language_code,
                "message_text": translation_payload["translated_message_text"],
                "provider_name": translation_payload["provider_name"],
                "model_name": translation_payload["model_name"],
                "prompt_version": translation_payload["prompt_version"],
                "usage_metadata": translation_payload["usage_metadata"],
                "prompt_fingerprint": translation_payload["prompt_fingerprint"],
            },
        }
    except RuntimeError:
        return {
            "translation_status": "failed",
            "target_language_code": target_language_code,
        }


def _read_selected_language_codes_for_user(cursor, user_id: int) -> list[str]:
    cursor.execute(
        """
        SELECT language.language_code
        FROM public.stephen_dcx_user_languages user_language
        JOIN public.stephen_dcx_languages language
          ON language.id = user_language.language_id
        WHERE user_language.user_id = %s
          AND language.is_active = TRUE
        ORDER BY user_language.sort_order ASC, language.language_code ASC
        """,
        (user_id,),
    )
    language_codes = [
        normalize_dcx_network_language_code(row[0])
        for row in cursor.fetchall()
    ]
    return [
        language_code
        for language_code in language_codes
        if language_code
    ]


def _read_network_author_payload(
    user_id: int,
    public_display_name: str | None,
    public_handle: str | None,
    public_identity_mode: str | None,
    profile_image_url: str | None,
) -> dict:
    public_handle_value = _read_public_handle(public_handle)
    public_identity_label = _read_network_public_identity_label(
        user_id=user_id,
        public_display_name=public_display_name,
        public_handle=public_handle_value,
        public_identity_mode=public_identity_mode,
    )
    return {
        "user_id": user_id,
        "public_display_name": public_display_name or "",
        "public_handle": public_handle_value,
        "public_identity_mode": public_identity_mode or "display_name",
        "public_identity_label": public_identity_label,
        "profile_image_url": profile_image_url or "",
    }


def _read_public_handle(value: str | None) -> str:
    return value.strip().lower().removeprefix("@") if isinstance(value, str) else ""


def _read_network_public_identity_label(
    user_id: int,
    public_display_name: str | None,
    public_handle: str | None,
    public_identity_mode: str | None,
) -> str:
    normalized_display_name = public_display_name.strip() if isinstance(public_display_name, str) else ""
    normalized_handle = _read_public_handle(public_handle)
    normalized_mode = public_identity_mode.strip() if isinstance(public_identity_mode, str) else ""

    if normalized_mode == "anonymous":
        return f"Trader #{user_id}"

    if normalized_mode == "handle" and normalized_handle:
        return f"@{normalized_handle}"

    if normalized_display_name:
        return normalized_display_name

    if normalized_handle:
        return f"@{normalized_handle}"

    return f"Trader #{user_id}"
