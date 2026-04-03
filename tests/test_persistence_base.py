from persistence.base import get_database_url, is_local_only_mode
from paths import DB_PATH


def test_local_only_mode_defaults_to_true(monkeypatch):
    monkeypatch.delenv("BSIE_LOCAL_ONLY", raising=False)

    assert is_local_only_mode() is True


def test_get_database_url_prefers_local_sqlite_when_local_only_enabled(monkeypatch):
    monkeypatch.setenv("BSIE_LOCAL_ONLY", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://bsie:bsie@127.0.0.1:5432/bsie")

    database_url, runtime_source = get_database_url()

    assert database_url == f"sqlite:///{DB_PATH}"
    assert runtime_source == "local_only_sqlite"


def test_get_database_url_uses_environment_when_local_only_disabled(monkeypatch):
    monkeypatch.setenv("BSIE_LOCAL_ONLY", "0")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://bsie:bsie@127.0.0.1:5432/bsie")

    database_url, runtime_source = get_database_url()

    assert database_url == "postgresql+psycopg://bsie:bsie@127.0.0.1:5432/bsie"
    assert runtime_source == "environment"
