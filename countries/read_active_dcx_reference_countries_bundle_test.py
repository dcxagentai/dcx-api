from countries.read_active_dcx_reference_countries_bundle import (
    read_active_dcx_reference_countries_bundle,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.query = query
        self.params = params

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._rows)


def test_returns_active_countries_with_nested_calling_codes() -> None:
    result = read_active_dcx_reference_countries_bundle(
        connect_to_database=lambda **_: _FakeConnection(
            [
                (10, "ES", "Spain", "es", 10, 101, "+34", True, 10),
                (11, "GB", "United Kingdom", "gb", 20, 102, "+44", True, 10),
                (11, "GB", "United Kingdom", "gb", 20, 103, "+440", False, 20),
            ]
        )
    )

    assert result["total_country_count"] == 2
    assert result["countries"][0]["country_code_alpha2"] == "ES"
    assert result["countries"][0]["calling_codes"] == [
        {
            "id": 101,
            "calling_code": "+34",
            "is_primary": True,
            "sort_order": 10,
        }
    ]
    assert result["countries"][1]["calling_codes"][1]["calling_code"] == "+440"


def test_returns_empty_bundle_when_no_active_countries_exist() -> None:
    result = read_active_dcx_reference_countries_bundle(
        connect_to_database=lambda **_: _FakeConnection([])
    )

    assert result == {
        "countries": [],
        "total_country_count": 0,
    }
