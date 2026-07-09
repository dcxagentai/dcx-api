from content.shared.build_dcx_slugified_text_identifier import (
    build_dcx_slugified_text_identifier,
)


def test_builds_ascii_slug_without_regression() -> None:
    assert build_dcx_slugified_text_identifier("WhatsApp Privacy Policy") == "whatsapp-privacy-policy"


def test_preserves_latin_diacritics_for_utf8_urls() -> None:
    assert (
        build_dcx_slugified_text_identifier("Política de Privacidade do WhatsApp")
        == "política-de-privacidade-do-whatsapp"
    )


def test_preserves_non_latin_native_script_slug_text() -> None:
    assert (
        build_dcx_slugified_text_identifier("व्हाट्सऐप गोपनीयता नीति")
        == "व्हाट्सऐप-गोपनीयता-नीति"
    )
    assert (
        build_dcx_slugified_text_identifier("سياسة خصوصية واتساب")
        == "سياسة-خصوصية-واتساب"
    )
    assert build_dcx_slugified_text_identifier("隐私政策") == "隐私政策"


def test_removes_url_structural_punctuation_from_one_path_segment() -> None:
    assert build_dcx_slugified_text_identifier("¿Qué es CIF/FOB?") == "qué-es-cif-fob"
