from messages.read_dcx_trade_interest_material_key import read_dcx_trade_interest_material_key


def test_matches_aluminum_ingots_to_aluminum_key() -> None:
    assert read_dcx_trade_interest_material_key("Primary Aluminium Ingots P1020A") == "aluminum"


def test_returns_none_for_unknown_material() -> None:
    assert read_dcx_trade_interest_material_key("rare specialty item") is None
