from __future__ import annotations

from pathlib import Path

from languages.export_live_dcx_public_ux_strings_bundle import (
    export_live_dcx_public_ux_strings_bundle,
)


def test_writes_generated_typescript_bundle_to_the_public_repo(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fake_api_file_path = tmp_path / "dcx_site" / "dcx_api" / "languages" / "export_live_dcx_public_ux_strings_bundle.py"
    fake_api_file_path.parent.mkdir(parents=True, exist_ok=True)
    fake_api_file_path.write_text("# placeholder", encoding="utf-8")

    monkeypatch.setattr(
        "languages.export_live_dcx_public_ux_strings_bundle.read_live_dcx_public_ux_strings_bundle",
        lambda: {
            "en": {"signup_form": {"email_label": "Email"}},
            "es": {"signup_form": {"email_label": "Correo electrónico"}},
            "fr": {"signup_form": {"email_label": "E-mail"}},
            "de": {"signup_form": {"email_label": "E-Mail"}},
        },
    )
    monkeypatch.setattr(
        "languages.export_live_dcx_public_ux_strings_bundle.Path.resolve",
        lambda self: fake_api_file_path,
    )

    generated_file_path = export_live_dcx_public_ux_strings_bundle()

    assert generated_file_path.name == "dcx_public_ux_strings_generated.ts"
    assert generated_file_path.exists()
    assert "dcx_public_ux_strings_generated" in generated_file_path.read_text(encoding="utf-8")
