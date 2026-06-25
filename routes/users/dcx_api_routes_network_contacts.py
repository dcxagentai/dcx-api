"""
CONTEXT:
This file owns the authenticated DCX Network contacts route.
Contacts are app-private trader profiles discoverable through search and follow/follower filters.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from auth.authorization.read_allowed_dcx_frontend_origin_or_error_response import (
    read_allowed_dcx_frontend_origin_or_error_response,
)
from auth.authorization.read_authenticated_dcx_user_id_or_error_response import (
    read_authenticated_dcx_user_id_or_error_response,
)
from network.dcx_network_capabilities import read_authenticated_dcx_network_contacts

dcx_api_routes_network_contacts_router = APIRouter(prefix="/network", tags=["network"])


@dcx_api_routes_network_contacts_router.get("/contacts", response_model=None)
def get_authenticated_dcx_network_contacts(
    request: Request,
    scope: str = "all",
    search: str = "",
):
    """
    CONTRACT:
      preconditions:
        - One authenticated DCX app session cookie is present.
      postconditions:
        - Returns searchable app-private contacts with follow/follower state.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - Traders need a direct way to discover people, follow them, and start DMs without waiting
          for posts to appear in the feed.
      WHEN TO USE it:
        - Use it from `/network/contacts`.
      WHEN NOT TO USE it:
        - Do not use it as an admin CRM/export endpoint.

    ERRORS:
      - API_DCX_NETWORK_CONTACTS_READ_FAILED:
          suggested_action: Retry in a moment after the backend is healthy.
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
        contacts_payload = read_authenticated_dcx_network_contacts(
            authenticated_user_id=authenticated_user_id,
            contact_scope=scope,
            search_query=search,
        )
    except RuntimeError:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "code": "API_DCX_NETWORK_CONTACTS_READ_FAILED",
                    "message": "We could not load network contacts right now.",
                    "suggested_action": "Retry in a moment after the backend is healthy.",
                },
            },
        )

    return {
        "ok": True,
        "data": contacts_payload,
        "context": {
            "surface": "app",
            "view": "network_contacts",
            "identity_resolution_mode": identity_resolution_mode,
        },
    }
