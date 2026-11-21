
"""Database connection and SQLAlchemy session management."""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

def normalize_database_url(url: str) -> str:
    """Pin an explicit PostgreSQL driver.

    SQLAlchemy 2.1 changed the default driver for ``postgresql://`` from
    psycopg2 to psycopg (v3).  Use whichever one is installed, preferring
    psycopg2 (listed in requirements.txt as psycopg2-binary).
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            rest = url[len(prefix):]
            try:
                import psycopg2  # noqa: F401

                return "postgresql+psycopg2://" + rest
            except ImportError:
                return "postgresql+psycopg://" + rest
    return url



def get_engine() -> Engine:
    """Create the database engine lazily."""
    global _engine, _session_factory

    if _engine is None:
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured. "
                "Set it in your local .env file."
            )

        _engine = create_engine(
            normalize_database_url(database_url),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        _session_factory = sessionmaker(
            bind=_engine,
            autoflush=False,
            expire_on_commit=False,
        )

    return _engine


def get_db() -> Generator[Session, None, None]:
    """Yield a session and always close it."""
    get_engine()

    if _session_factory is None:
        raise RuntimeError("Database session factory was not initialized.")

    db = _session_factory()

    try:
        yield db
    finally:
        db.close()


def check_database() -> dict[str, str]:
    """Check database connectivity and PostGIS availability."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
        postgis_version = connection.execute(
            text("SELECT PostGIS_Version()")
        ).scalar_one()

    return {
        "database": "connected",
        "postgis": postgis_version,
    }
