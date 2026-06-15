from unittest.mock import patch

import users.account.read_authenticated_dcx_user_account_summary as account_summary_module


class _FakeCursor:
    def __init__(self, fetchone_results, fetchall_results):
        self._fetchone_results = list(fetchone_results)
        self._fetchall_results = list(fetchall_results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchone(self):
        if not self._fetchone_results:
            return None
        return self._fetchone_results.pop(0)

    def fetchall(self):
        if not self._fetchall_results:
            return []
        return self._fetchall_results.pop(0)


class _FakeConnection:
    def __init__(self, fetchone_results, fetchall_results):
        self._fetchone_results = fetchone_results
        self._fetchall_results = fetchall_results

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._fetchone_results, self._fetchall_results)


def test_returns_account_summary_with_preferred_language_and_timezone_details() -> None:
    with patch.object(
        account_summary_module,
        "read_dcx_app_account_page_ux_strings_capability",
        return_value={
            "page_title": "Konto",
            "email_preference_no_email": "Keine E-Mails",
            "email_preference_newsletters": "Newsletter",
            "email_preference_all_email": "Alle E-Mails",
        },
    ), patch.object(
        account_summary_module,
        "read_authenticated_dcx_user_pending_whatsapp_phone_link",
        return_value={
            "phone_e164": "+34600000001",
            "challenge_status": "pending",
            "expires_at_ts_ms": 1775324931389,
            "sent_at_ts_ms": 1775324332389,
            "next_send_allowed_at_ts_ms": 1775324362389,
            "locked_until_ts_ms": None,
            "resend_count": 1,
            "send_count": 1,
            "last_resent_at_ts_ms": None,
        },
    ):
        result = account_summary_module.read_authenticated_dcx_user_account_summary_capability(
            authenticated_user_id=1,
            connect_to_database=lambda **_: _FakeConnection(
                [
                    (
                        1,
                        "caa94290-93cc-4fea-89ac-a4db936d5c8b",
                        "matbenet77@gmail.com",
                        True,
                        1775324331389,
                        "+34600000001",
                        True,
                        1775324300000,
                        "whatsapp",
                        "confirmed",
                        "newsletters",
                        1775324331389,
                        1773936459277,
                        1775324331563,
                        4,
                        "de",
                        "German",
                        "Deutsch",
                        False,
                        2,
                        "Europe/Madrid",
                        "(UTC+1/+2) Madrid",
                        "Europe",
                        "Stephen Trader",
                        "stephen_trader",
                        "handle",
                        "email",
                        1,
                        "Europe/London",
                        "(UTC+0/+1) London",
                        "Europe",
                        2,
                        "Europe/Madrid",
                        "(UTC+1/+2) Madrid",
                        "Europe",
                    )
                ],
                [
                    [
                        (1, "en", "English", "English", False),
                        (4, "de", "German", "Deutsch", False),
                    ],
                    [
                        (1, "Europe/London", "(UTC+0/+1) London", "Europe"),
                        (2, "Europe/Madrid", "(UTC+1/+2) Madrid", "Europe"),
                    ],
                    [
                        (
                            11,
                            "matbenet77@gmail.com",
                            "matbenet77@gmail.com",
                            "primary",
                            True,
                            True,
                            True,
                            True,
                            True,
                            1775324331389,
                            "email_otp",
                            True,
                            1775324331389,
                        )
                    ],
                    [
                        (
                            22,
                            "+34600000001",
                            "+34600000001",
                            "primary",
                            True,
                            False,
                            False,
                            False,
                            True,
                            1775324300000,
                            "whatsapp_link",
                            True,
                            1775324300000,
                            "whatsapp",
                        )
                    ],
                    [
                        ("aluminum", "Aluminum", 10),
                        ("wheat", "Wheat", 20),
                    ],
                    [
                        ("aluminum",),
                    ],
                ],
            ),
        )

    assert result == {
        "user_id": 1,
        "user_uuid": "caa94290-93cc-4fea-89ac-a4db936d5c8b",
        "primary_email": "matbenet77@gmail.com",
        "primary_email_confirmed": True,
        "primary_email_confirmed_at_ts_ms": 1775324331389,
        "primary_phone_e164": "+34600000001",
        "primary_phone_confirmed": True,
        "primary_phone_confirmed_at_ts_ms": 1775324300000,
        "primary_phone_channel": "whatsapp",
        "account_status": "confirmed",
        "email_communication_preference": "newsletters",
        "last_seen_at_ts_ms": 1775324331389,
        "created_at_ts_ms": 1773936459277,
        "updated_at_ts_ms": 1775324331563,
        "public_identity": {
            "public_display_name": "Stephen Trader",
            "public_handle": "stephen_trader",
            "public_identity_mode": "handle",
            "public_identity_label": "@stephen_trader",
        },
        "default_interaction_channel": "email",
        "preferred_language": {
            "id": 4,
            "language_code": "de",
            "language_name_en": "German",
            "language_name_native": "Deutsch",
            "is_rtl": False,
        },
        "preferred_timezone": {
            "id": 2,
            "iana_name": "Europe/Madrid",
            "display_label": "(UTC+1/+2) Madrid",
            "region_label": "Europe",
        },
        "email_contact_methods": [
            {
                "id": 11,
                "contact_value": "matbenet77@gmail.com",
                "normalized_value": "matbenet77@gmail.com",
                "display_label": "primary",
                "is_primary": True,
                "is_login_enabled": True,
                "is_recovery_enabled": True,
                "is_notification_enabled": True,
                "is_verified": True,
                "verified_at_ts_ms": 1775324331389,
                "verification_method": "email_otp",
                "is_active": True,
                "last_used_at_ts_ms": 1775324331389,
            }
        ],
        "phone_contact_methods": [
            {
                "id": 22,
                "contact_value": "+34600000001",
                "normalized_value": "+34600000001",
                "display_label": "primary",
                "is_primary": True,
                "is_login_enabled": False,
                "is_recovery_enabled": False,
                "is_notification_enabled": False,
                "is_verified": True,
                "verified_at_ts_ms": 1775324300000,
                "verification_method": "whatsapp_link",
                "is_active": True,
                "last_used_at_ts_ms": 1775324300000,
                "channel": "whatsapp",
                "current_channel_origin": None,
                "current_channel_confirmation": None,
                "requires_current_channel_confirmation": True,
            }
        ],
        "pending_whatsapp_phone_link": {
            "phone_e164": "+34600000001",
            "challenge_status": "pending",
            "expires_at_ts_ms": 1775324931389,
            "sent_at_ts_ms": 1775324332389,
            "next_send_allowed_at_ts_ms": 1775324362389,
            "locked_until_ts_ms": None,
            "resend_count": 1,
            "send_count": 1,
            "last_resent_at_ts_ms": None,
        },
        "available_languages": [
            {
                "id": 1,
                "language_code": "en",
                "language_name_en": "English",
                "language_name_native": "English",
                "is_rtl": False,
            },
            {
                "id": 4,
                "language_code": "de",
                "language_name_en": "German",
                "language_name_native": "Deutsch",
                "is_rtl": False,
            },
        ],
        "available_timezones": [
            {
                "id": 1,
                "iana_name": "Europe/London",
                "display_label": "(UTC+0/+1) London",
                "region_label": "Europe",
            },
            {
                "id": 2,
                "iana_name": "Europe/Madrid",
                "display_label": "(UTC+1/+2) Madrid",
                "region_label": "Europe",
            },
        ],
        "ux_strings": {
            "page_title": "Konto",
            "email_preference_no_email": "Keine E-Mails",
            "email_preference_newsletters": "Newsletter",
            "email_preference_all_email": "Alle E-Mails",
        },
        "available_email_communication_preferences": [
            {
                "value": "no_email",
                "label": "Keine E-Mails",
            },
            {
                "value": "newsletters",
                "label": "Newsletter",
            },
            {
                "value": "all_email",
                "label": "Alle E-Mails",
            },
        ],
        "available_public_identity_modes": [
            {
                "value": "display_name",
                "label": "Name",
            },
            {
                "value": "handle",
                "label": "Nickname",
            },
        ],
        "available_default_interaction_channels": [
            {
                "value": "app_only",
                "label": "App only",
            },
            {
                "value": "email",
                "label": "Email",
            },
            {
                "value": "whatsapp",
                "label": "WhatsApp",
            },
        ],
        "available_trade_interest_materials": [
            {
                "material_key": "aluminum",
                "display_label": "Aluminum",
                "sort_order": 10,
            },
            {
                "material_key": "wheat",
                "display_label": "Wheat",
                "sort_order": 20,
            },
        ],
        "selected_sidebar_clock_timezone_ids": [1, 2],
        "selected_sidebar_clock_timezones": [
            {
                "id": 1,
                "iana_name": "Europe/London",
                "display_label": "(UTC+0/+1) London",
                "region_label": "Europe",
            },
            {
                "id": 2,
                "iana_name": "Europe/Madrid",
                "display_label": "(UTC+1/+2) Madrid",
                "region_label": "Europe",
            },
        ],
        "selected_trade_interest_material_keys": ["aluminum"],
    }


def test_returns_account_summary_when_preferred_language_and_timezone_are_null() -> None:
    with patch.object(
        account_summary_module,
        "read_dcx_app_account_page_ux_strings_capability",
        return_value={
            "page_title": "Account",
            "email_preference_no_email": "No email",
            "email_preference_newsletters": "Newsletters",
            "email_preference_all_email": "All email",
        },
    ), patch.object(
        account_summary_module,
        "read_authenticated_dcx_user_pending_whatsapp_phone_link",
        return_value=None,
    ):
        result = account_summary_module.read_authenticated_dcx_user_account_summary_capability(
            authenticated_user_id=6,
            connect_to_database=lambda **_: _FakeConnection(
                [
                    (
                        6,
                        "57fd3e38-e777-4356-9dac-226d6d97495f",
                        "jill.whitney@ncmedia.ch",
                        True,
                        1774346486995,
                        None,
                        False,
                        None,
                        None,
                        "confirmed",
                        "newsletters",
                        1774346486995,
                        1774346415341,
                        1774346487162,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "",
                        "",
                        "anonymous",
                        "app_only",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    )
                ],
                [
                    [
                        (1, "en", "English", "English", False),
                        (2, "es", "Spanish", "Español", False),
                    ],
                    [
                        (1, "Europe/London", "(UTC+0/+1) London", "Europe"),
                        (2, "Europe/Madrid", "(UTC+1/+2) Madrid", "Europe"),
                    ],
                    [
                        (
                            31,
                            "jill.whitney@ncmedia.ch",
                            "jill.whitney@ncmedia.ch",
                            "primary",
                            True,
                            True,
                            True,
                            True,
                            True,
                            1774346486995,
                            "email_otp",
                            True,
                            1774346486995,
                        )
                    ],
                    [],
                    [],
                    [],
                ],
            ),
        )

    assert result["preferred_language"] is None
    assert result["preferred_timezone"] is None
    assert result["primary_phone_e164"] is None
    assert result["email_contact_methods"][0]["normalized_value"] == "jill.whitney@ncmedia.ch"
    assert result["phone_contact_methods"] == []
    assert result["default_interaction_channel"] == "app_only"
    assert result["available_trade_interest_materials"] == []
    assert result["selected_trade_interest_material_keys"] == []
    assert result["selected_sidebar_clock_timezone_ids"] == []
    assert result["selected_sidebar_clock_timezones"] == []
    assert result["ux_strings"]["page_title"] == "Account"
    assert result["user_id"] == 6
    assert len(result["available_languages"]) == 2
    assert len(result["available_timezones"]) == 2


def test_raises_clear_error_when_user_does_not_exist() -> None:
    try:
        account_summary_module.read_authenticated_dcx_user_account_summary_capability(
            authenticated_user_id=999,
            connect_to_database=lambda **_: _FakeConnection([None], [[], []]),
        )
    except RuntimeError as exc:
        assert str(exc) == "API_AUTHENTICATED_DCX_USER_ACCOUNT_NOT_FOUND"
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected missing user read to raise a stable runtime error.")
