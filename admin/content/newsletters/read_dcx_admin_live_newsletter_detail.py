"""
CONTEXT:
This file reads one live newsletter-content row detail for the DCX admin newsletter editor.
It exists so the admin frontend can open one newsletter/language editor route without using
query-string identity selectors.
"""

from __future__ import annotations

from typing import Any, Callable

import psycopg2

from admin.translations.build_dcx_admin_ai_translation_hash import (
    build_dcx_admin_ai_translation_content_hash,
)
from storage.db_config import DB_CONFIG


def read_dcx_admin_live_newsletter_detail_capability(
    email_key: str,
    language_code: str,
    send_audience_scope: str = "all",
    connect_to_database: Callable[..., Any] | None = None,
) -> dict:
    """
    CONTRACT:
      preconditions:
        - email_key is one non-empty stable newsletter identity.
        - language_code is one non-empty language code such as `en`.
        - send_audience_scope is one of `all`, `admins`, `devs`, or `shareholders`.
        - The configured database is reachable.
      postconditions:
        - Returns the current live newsletter row for the requested key/language pair.
        - Includes translation summary metadata and recipient-language readiness metadata for admin send decisions.
        - Readiness is calculated for the selected send audience scope.
        - Readiness excludes users whose current preference blocks newsletters or whose email address is actively suppressed for newsletter/all-email sends.
      side_effects: []
      idempotent: true
      retry_safe: true
      async: false

    NARRATIVE:
      WHY this exists:
        - The newsletter editor should open one explicit immutable live row rather than overloading
          the catalog response.
      WHEN TO USE it:
        - Use it from the admin `/content/newsletters/<language>/<email_key>` route only.
      WHEN NOT TO USE it:
        - Do not use it for transactional templates or send dispatch.
      WHAT CAN GO WRONG:
        - The requested newsletter row may not exist.
        - Database reads can fail.
      WHAT COMES NEXT:
        - The existing email save capability can continue editing this row because newsletter content
          still lives in `stephen_dcx_emails`.
        - The send-preparation surface can use the readiness metadata to warn about missing translations.

    TESTS:
      - returns_requested_live_newsletter_detail
      - reports_translation_gaps_for_newsletter_eligible_recipients
      - reports_translation_readiness_for_selected_audience_scope
      - raises_clear_error_when_live_newsletter_detail_missing

    ERRORS:
      - API_DCX_ADMIN_NEWSLETTER_DETAIL_NOT_FOUND:
          suggested_action: Return to the newsletters list, refresh it, and reopen the current live row.
          common_causes:
            - stale newsletter route
            - newsletter not yet created in the requested language
          recovery_steps:
            - Reload the newsletters catalog.
            - Retry from the current live row if needed.
          retry_safe: true
      - API_DCX_ADMIN_NEWSLETTER_DETAIL_READ_FAILED:
          suggested_action: Confirm database health and retry.
          common_causes:
            - database unavailable
            - query failure
          recovery_steps:
            - Verify database connectivity.
            - Retry once the backend is healthy.
          retry_safe: true

    CODE:
    """
    normalized_email_key = email_key.strip()
    normalized_language_code = language_code.strip().lower()
    normalized_send_audience_scope = send_audience_scope.strip().lower()
    if (
        normalized_email_key == ""
        or normalized_language_code == ""
        or normalized_send_audience_scope not in {"all", "admins", "devs", "shareholders"}
    ):
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_DETAIL_NOT_FOUND")

    connect = connect_to_database or psycopg2.connect

    try:
        with connect(**DB_CONFIG) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        e.id,
                        e.email_type,
                        e.email_key,
                        e.email_subject,
                        e.email_body,
                        e.is_original,
                        e.is_live,
                        e.version_of_id,
                        e.translation_of_id,
                        e.created_at_ts_ms,
                        e.updated_at_ts_ms,
                        l.id,
                        l.language_code,
                        l.language_name_en,
                        l.language_name_native,
                        l.is_rtl,
                        ai_translation_job.id,
                        ai_translation_job.source_row_id_snapshot,
                        ai_translation_job.source_content_hash,
                        ai_translation_job.updated_at_ts_ms
                    FROM stephen_dcx_emails e
                    INNER JOIN stephen_dcx_languages l
                      ON l.id = e.language_id
                    LEFT JOIN LATERAL (
                        SELECT
                            translation_job.id,
                            translation_job.source_row_id_snapshot,
                            translation_job.source_content_hash,
                            translation_job.updated_at_ts_ms
                        FROM stephen_dcx_ai_translation_jobs AS translation_job
                        WHERE translation_job.entity_kind = 'newsletter'
                          AND translation_job.target_row_id = e.id
                          AND translation_job.job_status = 'completed'
                        ORDER BY translation_job.id DESC
                        LIMIT 1
                    ) ai_translation_job
                      ON TRUE
                    WHERE e.is_live = TRUE
                      AND e.email_type = 'newsletter'
                      AND e.email_key = %s
                      AND l.language_code = %s
                    ORDER BY e.id DESC
                    LIMIT 1
                    """,
                    (normalized_email_key, normalized_language_code),
                )
                newsletter_row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT
                        language.id,
                        language.language_code,
                        language.language_name_en,
                        language.language_name_native,
                        language.is_rtl
                    FROM stephen_dcx_languages AS language
                    ORDER BY language.id ASC
                    """
                )
                supported_language_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        e.id,
                        e.email_subject,
                        e.is_original,
                        e.created_at_ts_ms,
                        e.updated_at_ts_ms,
                        l.id,
                        l.language_code,
                        l.language_name_en,
                        l.language_name_native,
                        l.is_rtl,
                        ai_translation_job.id,
                        ai_translation_job.source_row_id_snapshot,
                        ai_translation_job.source_content_hash,
                        ai_translation_job.updated_at_ts_ms
                    FROM stephen_dcx_emails AS e
                    INNER JOIN stephen_dcx_languages AS l
                      ON l.id = e.language_id
                    LEFT JOIN LATERAL (
                        SELECT
                            translation_job.id,
                            translation_job.source_row_id_snapshot,
                            translation_job.source_content_hash,
                            translation_job.updated_at_ts_ms
                        FROM stephen_dcx_ai_translation_jobs AS translation_job
                        WHERE translation_job.entity_kind = 'newsletter'
                          AND translation_job.target_row_id = e.id
                          AND translation_job.job_status = 'completed'
                        ORDER BY translation_job.id DESC
                        LIMIT 1
                    ) ai_translation_job
                      ON TRUE
                    WHERE e.email_type = 'newsletter'
                      AND e.email_key = %s
                      AND e.is_live = TRUE
                    ORDER BY l.id ASC, e.id DESC
                    """,
                    (normalized_email_key,),
                )
                translation_rows = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT
                        email_subject,
                        email_body
                    FROM stephen_dcx_emails
                    WHERE email_type = 'newsletter'
                      AND email_key = %s
                      AND is_original = TRUE
                      AND is_live = TRUE
                    LIMIT 1
                    """,
                    (normalized_email_key,),
                )
                original_content_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT
                        user_row.preferred_language_id,
                        primary_email_contact_method.normalized_value,
                        primary_email_contact_method.is_verified,
                        user_row.email_communication_preference,
                        user_row.account_status,
                        user_row.user_role,
                        EXISTS (
                            SELECT 1
                            FROM stephen_dcx_emails_suppressions AS suppression_row
                            WHERE suppression_row.is_active = TRUE
                              AND suppression_row.normalized_contact_value = primary_email_contact_method.normalized_value
                              AND suppression_row.suppression_scope IN ('newsletters', 'all_email')
                        ) AS has_newsletter_suppression
                    FROM stephen_dcx_users AS user_row
                    LEFT JOIN LATERAL (
                        SELECT
                            normalized_value,
                            is_verified
                        FROM stephen_dcx_users_contact_methods
                        WHERE user_id = user_row.id
                          AND contact_type = 'email'
                          AND is_primary = TRUE
                          AND is_active = TRUE
                        LIMIT 1
                    ) primary_email_contact_method
                      ON TRUE
                    WHERE (
                        %s = 'all'
                        OR (%s = 'admins' AND user_row.user_role = 'admin')
                        OR (%s = 'devs' AND user_row.user_role = 'dev')
                        OR (
                            %s = 'shareholders'
                            AND user_row.user_role IN ('shareholder', 'shareholders')
                        )
                    )
                    ORDER BY user_row.id ASC
                    """,
                    (
                        normalized_send_audience_scope,
                        normalized_send_audience_scope,
                        normalized_send_audience_scope,
                        normalized_send_audience_scope,
                    ),
                )
                user_rows = cursor.fetchall()
    except RuntimeError:
        raise
    except Exception as exc:  # pragma: no cover - integration path
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_DETAIL_READ_FAILED") from exc

    if newsletter_row is None:
        raise RuntimeError("API_DCX_ADMIN_NEWSLETTER_DETAIL_NOT_FOUND")

    language_by_id = {
        language_row[0]: {
            "id": language_row[0],
            "language_code": language_row[1],
            "language_name_en": language_row[2],
            "language_name_native": language_row[3],
            "is_rtl": language_row[4],
        }
        for language_row in supported_language_rows
    }
    english_language = next(
        (language for language in language_by_id.values() if language["language_code"] == "en"),
        None,
    )

    existing_translations = []
    available_language_codes = set()
    original_language_code = newsletter_row[12]
    original_email_id = newsletter_row[0]
    current_original_source_hash = _build_current_original_email_source_hash(
        selected_email_row=newsletter_row,
        original_content_row=original_content_row,
    )
    for translation_row in translation_rows:
        translation_language = {
            "id": translation_row[5],
            "language_code": translation_row[6],
            "language_name_en": translation_row[7],
            "language_name_native": translation_row[8],
            "is_rtl": translation_row[9],
        }
        available_language_codes.add(translation_language["language_code"])
        if translation_row[2] is True:
            original_language_code = translation_language["language_code"]
            original_email_id = translation_row[0]
        existing_translations.append(
            {
                "email_id": translation_row[0],
                "email_key": normalized_email_key,
                "email_subject": translation_row[1],
                "is_original": translation_row[2],
                "created_at_ts_ms": translation_row[3],
                "updated_at_ts_ms": translation_row[4],
                "is_current_language": translation_language["language_code"] == normalized_language_code,
                "language": translation_language,
                "ai_translation": _build_ai_translation_payload(
                    ai_translation_job_id=translation_row[10],
                    source_row_id_snapshot=translation_row[11],
                    source_content_hash=translation_row[12],
                    translated_at_ts_ms=translation_row[13],
                    current_original_source_hash=current_original_source_hash,
                ),
            }
        )

    missing_languages = []
    for language in language_by_id.values():
        if language["language_code"] in available_language_codes:
            continue
        missing_languages.append(language)

    readiness_by_language_code: dict[str, dict] = {}
    total_evaluated_recipient_count = 0
    total_send_candidate_count = 0
    total_blocked_missing_translation_count = 0

    for user_row in user_rows:
        recipient_email = (user_row[1] or "").strip()
        primary_email_confirmed = bool(user_row[2])
        email_communication_preference = (user_row[3] or "").strip().lower()
        account_status = (user_row[4] or "").strip().lower()
        has_newsletter_suppression = bool(user_row[6])
        if (
            recipient_email == ""
            or primary_email_confirmed is not True
            or email_communication_preference not in {"newsletters", "all_email"}
            or account_status != "confirmed"
            or has_newsletter_suppression is True
        ):
            continue

        total_evaluated_recipient_count += 1
        target_language = language_by_id.get(user_row[0]) or english_language
        if target_language is None:
            continue
        target_language_code = target_language["language_code"]
        readiness_row = readiness_by_language_code.setdefault(
            target_language_code,
            {
                "language": target_language,
                "eligible_recipient_count": 0,
                "send_candidate_count": 0,
                "blocked_missing_translation_count": 0,
                "has_live_translation": target_language_code in available_language_codes,
            },
        )
        readiness_row["eligible_recipient_count"] += 1
        if readiness_row["has_live_translation"]:
            readiness_row["send_candidate_count"] += 1
            total_send_candidate_count += 1
        else:
            readiness_row["blocked_missing_translation_count"] += 1
            total_blocked_missing_translation_count += 1

    readiness_rows = list(readiness_by_language_code.values())
    readiness_rows.sort(key=lambda row: row["language"]["id"])
    missing_readiness_languages = [
        {
            **row["language"],
            "blocked_missing_translation_count": row["blocked_missing_translation_count"],
        }
        for row in readiness_rows
        if row["blocked_missing_translation_count"] > 0
    ]

    return {
        "email_id": newsletter_row[0],
        "email_type": newsletter_row[1],
        "email_key": newsletter_row[2],
        "email_subject": newsletter_row[3],
        "email_body": newsletter_row[4],
        "is_original": newsletter_row[5],
        "is_live": newsletter_row[6],
        "version_of_id": newsletter_row[7],
        "translation_of_id": newsletter_row[8],
        "created_at_ts_ms": newsletter_row[9],
        "updated_at_ts_ms": newsletter_row[10],
        "language": {
            "id": newsletter_row[11],
            "language_code": newsletter_row[12],
            "language_name_en": newsletter_row[13],
            "language_name_native": newsletter_row[14],
            "is_rtl": newsletter_row[15],
        },
        "ai_translation": _build_ai_translation_payload(
            ai_translation_job_id=newsletter_row[16],
            source_row_id_snapshot=newsletter_row[17],
            source_content_hash=newsletter_row[18],
            translated_at_ts_ms=newsletter_row[19],
            current_original_source_hash=current_original_source_hash,
        ),
        "translation_summary": {
            "original_email_id": original_email_id,
            "original_language_code": original_language_code,
            "existing_translations": existing_translations,
            "missing_languages": missing_languages,
        },
        "language_readiness": {
            "send_audience_scope": normalized_send_audience_scope,
            "total_evaluated_recipient_count": total_evaluated_recipient_count,
            "total_send_candidate_count": total_send_candidate_count,
            "total_blocked_missing_translation_count": total_blocked_missing_translation_count,
            "language_rows": readiness_rows,
            "missing_languages": missing_readiness_languages,
        },
    }


def _build_current_original_email_source_hash(
    selected_email_row: tuple,
    original_content_row: tuple | None,
) -> str:
    if original_content_row is not None:
        fields = {
            "email_subject": original_content_row[0],
            "email_body": original_content_row[1],
        }
    else:
        fields = {
            "email_subject": selected_email_row[3],
            "email_body": selected_email_row[4],
        }
    return build_dcx_admin_ai_translation_content_hash(fields)


def _build_ai_translation_payload(
    ai_translation_job_id: int | None,
    source_row_id_snapshot: int | None,
    source_content_hash: str | None,
    translated_at_ts_ms: int | None,
    current_original_source_hash: str,
) -> dict:
    is_ai_translated = ai_translation_job_id is not None
    return {
        "is_ai_translated": is_ai_translated,
        "is_stale": bool(
            is_ai_translated
            and source_content_hash
            and source_content_hash != current_original_source_hash
        ),
        "job_id": ai_translation_job_id,
        "source_row_id_snapshot": source_row_id_snapshot,
        "translated_at_ts_ms": translated_at_ts_ms,
    }
