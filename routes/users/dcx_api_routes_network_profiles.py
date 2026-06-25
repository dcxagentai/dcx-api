"""
CONTEXT:
This file owns authenticated app routes for DCX Network profiles and follows.
Profiles remain app-private for now and are addressed by the user's lowercase nickname.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from network.dcx_network_capabilities import (
    read_authenticated_dcx_network_profile,
    set_authenticated_dcx_network_follow,
)

dcx_api_routes_network_profiles_router = APIRouter(prefix="/network", tags=["network"])


class DcxNetworkFollowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_follow: bool


@dcx_api_routes_network_profiles_router.get("/profiles/{network_nickname}", response_model=None)
def get_authenticated_dcx_network_profile(request: Request, network_nickname: str):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session cookie is present.
        - network_nickname is the URL nickname segment from `/network/{nickname}`.
      postconditions:
        - Returns one app-private DCX Network profile payload when found.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The app needs a clear profile read route for the new network surface without exposing
          public SEO pages yet.
      WHEN TO USE it:
        - Use it from the frontend profile page.
      WHEN NOT TO USE it:
        - Do not use it for admin CRM/user search.
      WHAT CAN GO WRONG:
        - The nickname may be invalid or missing.
        - The database may not have the network migration.
      WHAT COMES NEXT:
        - Public profile projection can be added through the Astro site later.

    TESTS:
      - No dedicated route tests exist yet; first slice is covered by compile and manual route smoke.

    ERRORS:
      - API_DCX_NETWORK_PROFILE_NOT_FOUND:
          suggested_action: Refresh the network page and retry with a current profile.
          common_causes:
            - stale nickname
            - malformed nickname
          recovery_steps:
            - Open a profile from the feed.
          retry_safe: true

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        profile_payload = read_authenticated_dcx_network_profile(
            authenticated_user_id=authenticated_user_id,
            network_nickname=network_nickname,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_PROFILE_READ_FAILED",
                    "message": "We could not load that network profile right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    if profile_payload is None:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_PROFILE_NOT_FOUND",
                    "message": "That network profile is not available.",
                    "suggested_action": "Refresh the network feed and retry with a current trader profile.",
                },
            },
        )

    return {
        "ok": True,
        "data": profile_payload,
        "context": {
            "surface": "app",
            "view": "network_profile",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }


@dcx_api_routes_network_profiles_router.post("/profiles/{network_nickname}/follow", response_model=None)
def post_authenticated_dcx_network_follow(
    request: Request,
    network_nickname: str,
    follow_request: DcxNetworkFollowRequest,
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session cookie is present.
        - network_nickname identifies another user profile.
      postconditions:
        - Saves the desired follow state.
        - Returns the refreshed profile payload.
      side_effects:
        - updates `stephen_dcx_network_follows`
      idempotent: true
      retry_safe: true
      async: false
      idempotency_key: network_follow:{authenticated_user_id}:{network_nickname}:{should_follow}
      locks:
        - unique network follow pair
      contention_strategy: delegate to the backend upsert capability

    NARRATIVE:
      WHY this exists:
        - Follows drive the default feed and give profiles a simple social signal.
      WHEN TO USE it:
        - Use it from profile follow/unfollow buttons.
      WHEN NOT TO USE it:
        - Do not use it as a block or notification preference.
      WHAT CAN GO WRONG:
        - The user can try to follow themselves.
        - The nickname can be stale.
      WHAT COMES NEXT:
        - Add blocks/mutes and notifications later.

    TESTS:
      - No dedicated route tests exist yet; first slice is covered by compile and manual route smoke.

    ERRORS:
      - API_DCX_NETWORK_FOLLOW_INVALID:
          suggested_action: Refresh the profile and retry.
          retry_safe: true

    CODE:
    """
    _, origin_error_response = read_allowed_dcx_frontend_origin_or_error_response(request)
    if origin_error_response is not None:
        return origin_error_response

    authenticated_user_id, identity_resolution_mode, error_response = (
        read_authenticated_dcx_user_id_or_error_response(request=request)
    )
    if error_response is not None:
        return error_response

    try:
        profile_payload = set_authenticated_dcx_network_follow(
            authenticated_user_id=authenticated_user_id,
            network_nickname=network_nickname,
            should_follow=follow_request.should_follow,
        )
    except RuntimeError as runtime_error:
        error_code = str(runtime_error)
        if error_code in {
            "API_DCX_NETWORK_PROFILE_NOT_FOUND",
            "API_DCX_NETWORK_FOLLOW_SELF",
        }:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": {
                        "code": "API_DCX_NETWORK_FOLLOW_INVALID",
                        "message": "We could not save that follow action.",
                        "suggested_action": "Refresh the profile and retry with another trader.",
                    },
                },
            )

        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_FOLLOW_SAVE_FAILED",
                    "message": "We could not save that follow action right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": profile_payload,
        "context": {
            "surface": "app",
            "view": "network_profile",
            "operation": "network_follow_saved",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
