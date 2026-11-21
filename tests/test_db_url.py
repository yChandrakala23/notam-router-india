"""SQLAlchemy 2.1 made psycopg (v3) the default driver for postgresql:// URLs;
api.db pins the driver that is actually installed."""

from api.db import normalize_database_url


def test_plain_url_gets_explicit_driver():
    url = normalize_database_url("postgresql://u:p@localhost:5433/notam")
    assert url.startswith(("postgresql+psycopg2://", "postgresql+psycopg://"))
    assert url.endswith("u:p@localhost:5433/notam")


def test_postgres_alias_and_explicit_driver():
    assert normalize_database_url("postgres://h/db").split("://")[1] == "h/db"
    assert normalize_database_url("postgresql+psycopg2://h/db") == "postgresql+psycopg2://h/db"
