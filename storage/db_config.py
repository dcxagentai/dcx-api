"""
CONTEXT:
This file resolves the database connection configuration for the project backend workspace.
It exists so the same backend code can:
- read a local `.env` file during development
- read real environment variables in production on Render
- support either a single database url or discrete connection fields

The exported `DB_CONFIG` value is intentionally kept compatible with the existing psycopg2
connection pattern used elsewhere in the backend.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def build_dcx_database_config_from_environment() -> dict[str, str]:
    """
    CONTRACT:
      preconditions:
        - Database environment variables are available either from the process environment or a local .env file.
      postconditions:
        - Returns a psycopg2-compatible connection config dictionary.
        - Uses PROMPTEO_DB_URL when present.
        - Otherwise returns a discrete-field config using the explicit PROMPTEO environment variable names.
        - Raises a stable runtime error when the required env contract is incomplete.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      why: 
        - This exists to remove literal database credentials from source files and let the same backend run locally and on Render.
        - This is an MVP project so lives in the Prompteo umbrella dev database with a xxxx_* prefixed set of project tables.
      when_to_use:
        - Whenever backend code needs Postgres connection settings.
        - During local development with a repo-local .env file.
        - During production deployment where Render injects environment variables.
      when_not_to_use:
        - Do not hardcode database credentials in backend capabilities once this config exists.
        - Do not bypass this file with ad hoc env lookups in unrelated modules unless there is a clear reason.
      what_can_go_wrong:
        - PROMPTEO_DB_URL may be missing or malformed.
        - The explicit discrete env vars may be missing required values.
        - A local .env file may contain stale values.
      what_comes_next:
        - Reuse this same config path for the Render Postgres plumbing proof.
        - Later extend this only if the project adopts multiple databases or read/write split config.

    TESTS:
      - returns_dsn_config_when_database_url_is_present
      - returns_discrete_config_when_database_url_is_absent

    ERRORS:
      - API_DB_CONFIG_ENV_MISSING:
          suggested_action: Add PROMPTEO_DB_URL or the required DCX DB env vars locally or on Render.
          suggested_action: Add PROMPTEO_DB_URL or the required PROMPTEO DB env vars locally or on Render.
          common_causes:
            - .env file missing locally
            - Render service env vars not configured yet
            - variable names mistyped
          recovery_steps:
            - Add or correct PROMPTEO_DB_URL, or set PROMPTEO_DB_NAME / PROMPTEO_DB_USER / PROMPTEO_DB_PASSWORD / PROMPTEO_DB_HOST / PROMPTEO_DB_PORT.
            - Restart the backend so it reloads environment variables.
          retry_safe: true

    CODE:
    """
    database_url = os.getenv("PROMPTEO_DB_URL")

    if database_url:
        return {"dsn": database_url}

    db_name = os.getenv("PROMPTEO_DB_NAME")
    db_user = os.getenv("PROMPTEO_DB_USER")
    db_password = os.getenv("PROMPTEO_DB_PASSWORD")
    db_host = os.getenv("PROMPTEO_DB_HOST")
    db_port = os.getenv("PROMPTEO_DB_PORT")
    db_sslmode = os.getenv("PROMPTEO_DB_SSLMODE")

    config: dict[str, str] = {
        "dbname": db_name,
        "user": db_user,
        "password": db_password,
        "host": db_host,
        "port": db_port,
    }

    missing_required_fields = [
        field_name
        for field_name, field_value in config.items()
        if field_value in {None, ""}
    ]

    if missing_required_fields:
        raise RuntimeError(
            "API_DB_CONFIG_ENV_MISSING:"
            + ",".join(missing_required_fields)
        )

    if db_sslmode:
        config["sslmode"] = db_sslmode

    return config


DB_CONFIG: Final[dict[str, str]] = build_dcx_database_config_from_environment()
