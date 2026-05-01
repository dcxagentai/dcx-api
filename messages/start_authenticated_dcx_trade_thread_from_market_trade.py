"""
CONTEXT:
This file starts or reuses a private conversation thread for a public market trade.
It creates the minimum thread spine needed for trader-to-trader discussion in MVP.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json

from storage.db_config import DB_CONFIG


def start_authenticated_dcx_trade_thread_from_market_trade(
    authenticated_user_id: int,
    trade_publication_id: int,
    connect_to_database: Callable[..., Any] | None = None,
) -> dict | None:
    connect = connect_to_database or psycopg2.connect
    now_ts_ms = int(time.time() * 1000)

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        publication.id,
                        publication.trade_id,
                        publication.owner_user_id
                    FROM stephen_dcx_trade_publications publication
                    WHERE publication.id = %s
                      AND publication.publication_status = 'active'
                      AND publication.visibility_status IN ('shareable', 'public')
                    LIMIT 1
                    """,
                    (trade_publication_id,),
                )
                publication_row = cursor.fetchone()
                if publication_row is None:
                    return None
                if publication_row[2] == authenticated_user_id:
                    raise RuntimeError("API_DCX_TRADE_THREAD_SELF_NOT_ALLOWED")

                cursor.execute(
                    """
                    SELECT id, thread_reference_code, thread_status
                    FROM stephen_dcx_trade_threads
                    WHERE trade_id = %s
                      AND counterparty_user_id = %s
                      AND thread_status IN ('open', 'closed')
                    LIMIT 1
                    """,
                    (publication_row[1], authenticated_user_id),
                )
                existing_thread_row = cursor.fetchone()
                if existing_thread_row is not None:
                    return {
                        "trade_thread_id": existing_thread_row[0],
                        "thread_reference_code": existing_thread_row[1],
                        "thread_status": existing_thread_row[2],
                        "trade_id": publication_row[1],
                        "trade_publication_id": publication_row[0],
                        "owner_user_id": publication_row[2],
                        "counterparty_user_id": authenticated_user_id,
                    }

                temporary_reference_code = f"C_PENDING_{uuid.uuid4().hex}"
                cursor.execute(
                    """
                    INSERT INTO stephen_dcx_trade_threads (
                        trade_id,
                        trade_publication_id,
                        owner_user_id,
                        counterparty_user_id,
                        thread_status,
                        thread_reference_code,
                        thread_metadata_json,
                        created_at_ts_ms,
                        updated_at_ts_ms
                    )
                    VALUES (%s, %s, %s, %s, 'open', %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        publication_row[1],
                        publication_row[0],
                        publication_row[2],
                        authenticated_user_id,
                        temporary_reference_code,
                        Json({}),
                        now_ts_ms,
                        now_ts_ms,
                    ),
                )
                thread_id = cursor.fetchone()[0]
                thread_reference_code = f"C{thread_id}"
                cursor.execute(
                    """
                    UPDATE stephen_dcx_trade_threads
                    SET thread_reference_code = %s
                    WHERE id = %s
                    """,
                    (thread_reference_code, thread_id),
                )

        return {
            "trade_thread_id": thread_id,
            "thread_reference_code": thread_reference_code,
            "thread_status": "open",
            "trade_id": publication_row[1],
            "trade_publication_id": publication_row[0],
            "owner_user_id": publication_row[2],
            "counterparty_user_id": authenticated_user_id,
        }
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("API_DCX_TRADE_THREAD_START_FAILED") from exc
