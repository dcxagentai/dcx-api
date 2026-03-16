"""
CONTEXT:
This file is the minimal FastAPI application root for the DCX API workspace.
It exists to prove that the backend repo root can now function as the real local API app root,
while preserving the existing git repo and context folders.

The main capabilities exposed here are:
- a root hello-world route returning the canonical runtime success wrapper shape
- a shared welcome-message route consumed by the three frontend hello-world shells
- a read-only local Postgres sample projected into that shared bootstrap route
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dcx_api_read_latest_raw_message_from_local_postgres_bootstrap_capability import (
    read_latest_raw_message_from_local_postgres_bootstrap_capability,
)

app = FastAPI(title="DCX API Bootstrap", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def get_dcx_api_hello_world_response() -> dict:
    """
    CONTRACT:
      preconditions:
        - The FastAPI application is running and able to receive HTTP requests.
      postconditions:
        - Returns a canonical success wrapper confirming the DCX API hello-world route is live.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why: This exists to prove the backend workspace is now a real FastAPI app root before real APIs, webhooks, and storage integrations are added.
      when_to_use:
        - During local smoke testing of the backend workspace.
        - During initial deployment verification of the API service shell.
      when_not_to_use:
        - Do not use this as the long-term health or readiness contract once real service checks exist.
        - Do not use this route for domain behavior beyond bootstrap verification.
      what_can_go_wrong:
        - The service may fail to start because dependencies are missing.
        - The route may fail if the ASGI app is imported from the wrong module path.
      what_comes_next:
        - Add dedicated health/readiness routes.
        - Add the first real domain capabilities and project them through API routes.

    TESTS:
      - root_route_returns_ok_wrapper: GET / -> response json has ok=true and hello-world payload
      - root_route_returns_backend_identity: GET / -> response json identifies dcx_api backend bootstrap state
      - root_route_is_side_effect_free: repeated GET / calls -> same response payload structure without external mutation

    ERRORS:
      - API_HELLO_WORLD_IMPORT_FAILURE:
          suggested_action: Confirm FastAPI and uvicorn are installed and the server is launched from the dcx_api repo root.
          common_causes:
            - requirements were not installed
            - uvicorn target module path is wrong
          recovery_steps:
            - Run pip install -r requirements.txt in the intended environment.
            - Start the server with uvicorn dcx_api_fastapi_hello_world_application:app --reload.
          retry_safe: true

    CODE:
    """
    return {
        "ok": True,
        "data": {
            "service_name": "dcx_api",
            "status": "ready",
            "message": "DCX API backend hello world",
        },
        "context": {
            "what_happened": "The backend hello-world route responded successfully.",
            "side_effects_executed": [],
            "next_steps": [
                "Install real API capabilities.",
                "Add health, auth, and storage integrations.",
            ],
            "related_operations": [
                "run_uvicorn_for_local_backend_dev",
                "add_first_real_fastapi_capability",
            ],
        },
    }


@app.get("/api/bootstrap/welcome")
def get_dcx_api_shared_frontend_welcome_message_response() -> dict:
    """
    CONTRACT:
      preconditions:
        - The FastAPI application is running and able to receive HTTP requests from local frontend origins.
        - The local stephen_dcx database is reachable for one read-only bootstrap query.
      postconditions:
        - Returns a canonical success wrapper containing the shared welcome message consumed by the frontend hello-world shells.
        - Includes one real local Postgres raw-message sample for bootstrap proof.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why: This exists to prove that all three frontend shells can call a real backend route and render the same backend-provided message plus one real local Postgres sample through a shared branding element.
      when_to_use:
        - During local integration testing of the public, app, and admin hello-world shells.
        - During early backend/frontend wiring before real domain routes exist.
      when_not_to_use:
        - Do not use this route as the long-term home of user-facing welcome or onboarding content.
        - Do not use this route for auth or stateful capability testing.
      what_can_go_wrong:
        - Browser calls may fail if local frontend origins are not allowed by CORS.
        - The local Postgres query may fail if the bootstrap database is unavailable.
        - The frontend shared branding component may display an error state if the route is unavailable.
      what_comes_next:
        - Replace this with the first real domain routes.
        - Reuse the same frontend/backend integration pattern for real capabilities.

    TESTS:
      - welcome_route_returns_ok_wrapper: GET /api/bootstrap/welcome -> response json has ok=true and welcome payload
      - welcome_route_returns_shared_message: GET /api/bootstrap/welcome -> response json contains the expected shared frontend welcome string
      - welcome_route_returns_latest_raw_message_payload_shape: GET /api/bootstrap/welcome -> response json contains latest_raw_message with bootstrap fields
      - welcome_route_allows_local_frontend_origin: GET /api/bootstrap/welcome with localhost Origin header -> access-control-allow-origin is returned

    ERRORS:
      - API_SHARED_WELCOME_CORS_MISCONFIGURED:
          suggested_action: Re-check FastAPI CORSMiddleware configuration for localhost development origins.
          common_causes:
            - local frontend port not matched by origin rules
            - middleware removed or configured too narrowly
          recovery_steps:
            - Restore CORSMiddleware with localhost and 127.0.0.1 origin support.
            - Re-run the local frontend against the backend route.
          retry_safe: true
      - API_BOOTSTRAP_LOCAL_POSTGRES_UNAVAILABLE:
          suggested_action: Confirm local Postgres is running and dcx_storage.db_config.py still points to the real local bootstrap database.
          common_causes:
            - local Postgres service stopped
            - wrong db_config credentials
            - stephen_dcx database missing
          recovery_steps:
            - Start local Postgres.
            - Re-check db_config.py.
            - Retry the route once the database is reachable.
          retry_safe: true

    CODE:
    """
    latest_raw_message = read_latest_raw_message_from_local_postgres_bootstrap_capability()

    return {
        "ok": True,
        "data": {
            "message": "Welcome to the connected DCX MVP shell.",
            "latest_raw_message": latest_raw_message,
        },
        "context": {
            "what_happened": "The backend shared welcome route responded successfully and included one real local Postgres raw-message sample.",
            "side_effects_executed": [],
            "next_steps": [
                "Render this message and local database sample in the shared frontend branding component.",
                "Replace this route with the first real domain capability when ready.",
            ],
            "related_operations": [
                "render_shared_backend_welcome_banner",
                "read_latest_raw_message_from_local_postgres_bootstrap_capability",
                "replace_bootstrap_routes_with_real_capabilities",
            ],
        },
    }
