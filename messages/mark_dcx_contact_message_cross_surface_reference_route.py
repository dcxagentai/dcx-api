from __future__ import annotations

import time
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from storage.db_config import DB_CONFIG


def mark_dcx_contact_message_cross_surface_reference_routed(
    contact_message_id: int,
    reference_kind: str,
    reference_code: str,
    route_summary_text: str,
    route_metadata_json: dict,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    normalized_reference_kind = reference_kind.strip().lower() if isinstance(reference_kind, str) else ""
    normalized_reference_code = reference_code.strip().upper() if isinstance(reference_code, str) else ""
    normalized_summary = route_summary_text.strip() if isinstance(route_summary_text, str) else ""
    now_ts_ms = int(time.time() * 1000)
    connect = connect_to_database or psycopg2.connect

    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE stephen_dcx_contact_messages
                SET
                    processing_status = 'ready',
                    derivation_status = 'completed',
                    analysis_status = 'completed',
                    analysis_summary_text = %s,
                    workflow_classification_status = 'completed',
                    primary_workflow_kind = NULL,
                    contains_trade_items = FALSE,
                    contains_market_topic_items = FALSE,
                    contains_other_items = FALSE,
                    workflow_reason_summary = %s,
                    workflow_metadata_json = COALESCE(workflow_metadata_json, '{}'::jsonb) || %s::jsonb,
                    analysis_completed_at_ts_ms = %s,
                    updated_at_ts_ms = %s
                WHERE id = %s
                """,
                (
                    normalized_summary,
                    normalized_summary,
                    Json(
                        {
                            "cross_surface_reference_routing": {
                                "routed": True,
                                "reference_kind": normalized_reference_kind,
                                "reference_code": normalized_reference_code,
                                **route_metadata_json,
                            }
                        }
                    ),
                    now_ts_ms,
                    now_ts_ms,
                    contact_message_id,
                ),
            )

    return {
        "routed": True,
        "reference_kind": normalized_reference_kind,
        "reference_code": normalized_reference_code,
        "processing_status": "ready",
        "derivation_status": "completed",
    }


def mark_dcx_contact_message_cross_surface_reference_unroutable(
    contact_message_id: int,
    reference_kind: str,
    reference_code: str,
    reason_code: str,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    normalized_reference_kind = reference_kind.strip().lower() if isinstance(reference_kind, str) else ""
    normalized_reference_code = reference_code.strip().upper() if isinstance(reference_code, str) else ""
    normalized_reason_code = reason_code.strip().lower() if isinstance(reason_code, str) else "invalid_reference"
    now_ts_ms = int(time.time() * 1000)
    connect = connect_to_database or psycopg2.connect
    summary_text = f"Could not route cross-surface reference {normalized_reference_code}."

    with connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE stephen_dcx_contact_messages
                SET
                    processing_status = 'ready',
                    derivation_status = 'completed',
                    analysis_status = 'completed',
                    analysis_summary_text = %s,
                    workflow_classification_status = 'completed',
                    primary_workflow_kind = NULL,
                    contains_trade_items = FALSE,
                    contains_market_topic_items = FALSE,
                    contains_other_items = TRUE,
                    workflow_reason_summary = %s,
                    workflow_metadata_json = COALESCE(workflow_metadata_json, '{}'::jsonb) || %s::jsonb,
                    analysis_completed_at_ts_ms = %s,
                    updated_at_ts_ms = %s
                WHERE id = %s
                """,
                (
                    summary_text,
                    summary_text,
                    Json(
                        {
                            "cross_surface_reference_routing": {
                                "routed": False,
                                "reference_kind": normalized_reference_kind,
                                "reference_code": normalized_reference_code,
                                "reason_code": normalized_reason_code,
                            }
                        }
                    ),
                    now_ts_ms,
                    now_ts_ms,
                    contact_message_id,
                ),
            )

    return {
        "routed": False,
        "reference_kind": normalized_reference_kind,
        "reference_code": normalized_reference_code,
        "reason_code": normalized_reason_code,
        "processing_status": "ready",
        "derivation_status": "completed",
    }
