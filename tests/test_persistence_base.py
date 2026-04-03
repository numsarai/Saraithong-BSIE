from persistence.base import get_database_url, is_local_only_mode
from paths import DB_PATH


def test_local_only_mode_defaults_to_true(monkeypatch):
    assert is_local_only_mode() is True


def test_get_database_url_is_always_local_sqlite():
    database_url, runtime_source = get_database_url()

    assert database_url == f"sqlite:///{DB_PATH}"
    assert runtime_source == "local_sqlite"
