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
        return_value={"page_title": "Konto"},
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
                        "announcements",
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
        "email_communication_preference": "announcements",
        "last_seen_at_ts_ms": 1775324331389,
        "created_at_ts_ms": 1773936459277,
        "updated_at_ts_ms": 1775324331563,
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
        },
        "available_email_communication_preferences": [
            {
                "value": "announcements",
                "label": "Announcements",
            },
            {
                "value": "essential_only",
                "label": "Essential only",
            },
        ],
    }


def test_returns_account_summary_when_preferred_language_and_timezone_are_null() -> None:
    with patch.object(
        account_summary_module,
        "read_dcx_app_account_page_ux_strings_capability",
        return_value={"page_title": "Account"},
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
                        "announcements",
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
                ],
            ),
        )

    assert result["preferred_language"] is None
    assert result["preferred_timezone"] is None
    assert result["primary_phone_e164"] is None
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
