from pathlib import Path

from app.settings import Settings, choose_env_file


def test_couchdb_url_uses_environment():
    s = Settings(
        COUCHDB_USERNAME="u",
        COUCHDB_PASSWORD="p",
        COUCHDB_HOST="h",
        COUCHDB_PORT=1234,
    )
    assert s.couchdb_url == "http://u:p@h:1234"


def test_postgres_url_uses_environment():
    s = Settings(
        POSTGRES_USERNAME="user",
        POSTGRES_PASSWORD="pw",
        POSTGRES_HOST="db",
        POSTGRES_PORT=5555,
        POSTGRES_DATABASE="appdb",
    )
    assert s.postgres_url == "postgresql://user:pw@db:5555/appdb"


def test_choose_env_file_prefers_env_local(monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda self: str(self) == ".env.local")
    assert choose_env_file() == ".env.local"


def test_choose_env_file_falls_back(monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda self: False)
    assert choose_env_file() == ".env"
