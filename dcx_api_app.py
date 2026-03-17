"""
CONTEXT:
This file is the minimal FastAPI application root for the DCX API workspace.
It exists to prove that the backend repo root can now function as the real local API app root,
while preserving the existing git repo and context folders.

The main capabilities exposed here are:
- a root welcome route consumed by the three frontend hello-world shells
- a read-only local Postgres sample projected from the fresh one-table bootstrap schema into that route
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dcx_api_read_latest_bootstrap_test_message_from_local_postgres_capability import (
    read_latest_bootstrap_test_message_from_local_postgres_capability,
)

app = FastAPI(title="DCX API Bootstrap", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$|^https://dcx-(admin|app|public)\.pages\.dev$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def get_dcx_api_root_welcome_response() -> dict:
    """
    CONTRACT:
      preconditions:
        - The FastAPI application is running and able to receive HTTP requests from local frontend origins.
        - The configured Postgres database is reachable for one read-only bootstrap query.
      postconditions:
        - Returns a canonical success wrapper containing the backend welcome payload for the bootstrap shell.
        - Includes one real Postgres bootstrap-test-message sample for plumbing proof.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why: This exists to make the backend base URL itself useful as the first plumbing-proof route for local development and production on api.dcx.com.
      when_to_use:
        - During local smoke testing of the backend workspace.
        - During initial deployment verification of the API service shell.
        - When the frontend bootstrap shells need one simple backend base URL to call.
      when_not_to_use:
        - Do not use this as the long-term health or readiness contract once real service checks exist.
        - Do not use this route as the final home for user-facing welcome or onboarding content.
      what_can_go_wrong:
        - The service may fail to start because dependencies are missing.
        - The route may fail if the ASGI app is imported from the wrong module path.
        - The bootstrap database query may fail if the database is unavailable.
        - Browser calls from hosted frontend shells may fail if CORS does not allow the current Pages origins.
      what_comes_next:
        - Add dedicated health/readiness routes.
        - Add the first real domain capabilities and project them through API routes.

    TESTS:
      - root_route_returns_ok_wrapper: GET / -> response json has ok=true and backend welcome payload
      - root_route_returns_backend_identity: GET / -> response json identifies dcx_api backend bootstrap state
      - root_route_returns_latest_raw_message_payload_shape: GET / -> response json contains latest_raw_message with bootstrap fields
      - root_route_allows_local_frontend_origin: GET / with localhost Origin header -> access-control-allow-origin is returned
      - root_route_allows_cloudflare_pages_frontend_origin: GET / with dcx-admin.pages.dev Origin header -> access-control-allow-origin is returned

    ERRORS:
      - API_HELLO_WORLD_IMPORT_FAILURE:
          suggested_action: Confirm FastAPI and uvicorn are installed and the server is launched from the dcx_api repo root.
          common_causes:
            - requirements were not installed
            - uvicorn target module path is wrong
          recovery_steps:
            - Run pip install -r requirements.txt in the intended environment.
            - Start the server with uvicorn dcx_api_app:app --reload.
          retry_safe: true
      - API_BOOTSTRAP_TEST_MESSAGE_LOCAL_POSTGRES_UNAVAILABLE:
          suggested_action: Confirm local Postgres is running and the bootstrap test schema was applied to the configured database.
          common_causes:
            - local Postgres service stopped
            - wrong db_config credentials
            - bootstrap test schema not applied yet
          recovery_steps:
            - Start local Postgres.
            - Re-check db_config.py.
            - Run the bootstrap test schema apply script.
            - Retry the route once the database is reachable.
          retry_safe: true
      - API_SHARED_WELCOME_CORS_MISCONFIGURED:
          suggested_action: Confirm the temporary MVP CORS rule still allows localhost and the three Cloudflare Pages frontend origins.
          common_causes:
            - CORS origin regex too narrow
            - Pages project hostnames changed
            - middleware configuration edited without updating tests
          recovery_steps:
            - Re-check the allow_origin_regex in dcx_api_app.py.
            - Confirm the frontend is deployed on the expected pages.dev hostname.
            - Retry after redeploying the backend.
          retry_safe: true

    CODE:
    """
    latest_raw_message = read_latest_bootstrap_test_message_from_local_postgres_capability()

    return {
        "ok": True,
        "data": {
            "service_name": "dcx_api",
            "status": "ready",
            "message": "Welcome to the connected DCX MVP shell.",
            "latest_raw_message": latest_raw_message,
        },
        "context": {
            "what_happened": "The backend root route responded successfully and included one real Postgres bootstrap test message sample.",
            "side_effects_executed": [],
            "next_steps": [
                "Render this message and local database sample in the shared frontend branding component.",
                "Replace this route with the first real domain capability when the fresh MVP schema is ready.",
            ],
            "related_operations": [
                "render_shared_backend_welcome_banner",
                "read_latest_bootstrap_test_message_from_local_postgres_capability",
                "replace_bootstrap_routes_with_real_capabilities",
            ],
        },
    }
