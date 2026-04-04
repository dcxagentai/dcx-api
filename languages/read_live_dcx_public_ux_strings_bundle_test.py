from __future__ import annotations

from languages.read_live_dcx_public_ux_strings_bundle import (
    read_live_dcx_public_ux_strings_bundle,
)


class _FakeCursor:
    def __init__(self, rows: list[tuple[str, str, str, str]]) -> None:
        self._rows = rows

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query: str, params: tuple[list[str], list[str]]) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[tuple[str, str, str, str]]:
        return self._rows


class _FakeConnection:
    def __init__(self, rows: list[tuple[str, str, str, str]]) -> None:
        self._rows = rows

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._rows)


def test_builds_language_first_bundle_from_live_rows(monkeypatch) -> None:
    fake_rows = [
        ("en", "signup_form", "email_label", "Email"),
        ("es", "signup_form", "email_label", "Correo electrónico"),
        ("fr", "signup_otp_form", "restart_button_label", "Retour à l’inscription"),
        ("de", "signup_confirmation_page", "return_link_label", "Zurück zum Start"),
    ]

    monkeypatch.setattr(
        "languages.read_live_dcx_public_ux_strings_bundle.psycopg2.connect",
        lambda **kwargs: _FakeConnection(fake_rows),
    )

    bundle = read_live_dcx_public_ux_strings_bundle()

    assert bundle["en"]["signup_form"]["email_label"] == "Email"
    assert bundle["es"]["signup_form"]["email_label"] == "Correo electrónico"
    assert bundle["fr"]["signup_otp_form"]["restart_button_label"] == "Retour à l’inscription"
    assert bundle["de"]["signup_confirmation_page"]["return_link_label"] == "Zurück zum Start"


def test_ignores_non_live_rows_and_unknown_groups(monkeypatch) -> None:
    fake_rows = [
        ("en", "signup_form", "email_label", "Email"),
    ]

    monkeypatch.setattr(
        "languages.read_live_dcx_public_ux_strings_bundle.psycopg2.connect",
        lambda **kwargs: _FakeConnection(fake_rows),
    )

    bundle = read_live_dcx_public_ux_strings_bundle()

    assert bundle["en"]["signup_form"]["email_label"] == "Email"
    assert bundle["en"]["home"] == {}
    assert bundle["es"]["signup_form"] == {}
