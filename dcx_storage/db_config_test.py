"""
CONTEXT:
This file verifies the database configuration resolution logic for the DCX API workspace.
It keeps the local-vs-production env precedence behavior executable next to the config module.
"""

from dcx_storage.db_config import build_dcx_database_config_from_environment


def test_returns_dsn_config_when_database_url_is_present(monkeypatch) -> None:
    monkeypatch.setenv("PROMPTEO_DB_URL", "postgresql://user:pass@host:5432/dbname")
    monkeypatch.delenv("PROMPTEO_DB_NAME", raising=False)

    config = build_dcx_database_config_from_environment()

    assert config == {"dsn": "postgresql://user:pass@host:5432/dbname"}


def test_returns_discrete_config_when_database_url_is_absent(monkeypatch) -> None:
    monkeypatch.delenv("PROMPTEO_DB_URL", raising=False)
    monkeypatch.setenv("PROMPTEO_DB_NAME", "stephen_dcx")
    monkeypatch.setenv("PROMPTEO_DB_USER", "postgres")
    monkeypatch.setenv("PROMPTEO_DB_PASSWORD", "1234")
    monkeypatch.setenv("PROMPTEO_DB_HOST", "localhost")
    monkeypatch.setenv("PROMPTEO_DB_PORT", "5432")

    config = build_dcx_database_config_from_environment()

    assert config["dbname"] == "stephen_dcx"
    assert config["user"] == "postgres"
    assert config["password"] == "1234"
    assert config["host"] == "localhost"
    assert config["port"] == "5432"


def test_raises_clear_error_when_required_prompteo_fields_are_missing(monkeypatch) -> None:
    monkeypatch.delenv("PROMPTEO_DB_URL", raising=False)
    monkeypatch.delenv("PROMPTEO_DB_NAME", raising=False)
    monkeypatch.delenv("PROMPTEO_DB_USER", raising=False)
    monkeypatch.delenv("PROMPTEO_DB_PASSWORD", raising=False)
    monkeypatch.delenv("PROMPTEO_DB_HOST", raising=False)
    monkeypatch.delenv("PROMPTEO_DB_PORT", raising=False)

    try:
        build_dcx_database_config_from_environment()
    except RuntimeError as exc:
        assert str(exc).startswith("API_DB_CONFIG_ENV_MISSING:")
        assert "dbname" in str(exc)
        assert "password" in str(exc)
    else:  # pragma: no cover - explicit falsification branch
        raise AssertionError("Expected missing PROMPTEO env vars to raise a runtime error.")
