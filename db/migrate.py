"""Apply SQL migrations in db/migrations/ in order (idempotent), and check setup.

Owner: Person A.

    python -m db.migrate --check     # connection, versions, extensions, tables (read-only)
    python -m db.migrate             # apply pending migrations
    python -m db.migrate --status    # list applied / pending

Reads DATABASE_URL from .env.  Never prints the password.  Never drops
anything: every migration file is written to be re-runnable.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

EXPECTED_TABLES = [
    "data_source", "ingestion_run", "raw_notam", "fir", "airport", "notam_event",
    "waypoint", "airway", "airway_edge", "route_request", "candidate_route",
    "route_conflict",
]


def database_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set (copy .env.example to .env and edit it).")
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
    return url


def safe_target(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.username}@{parsed.hostname}:{parsed.port or 5432}{parsed.path}"


def connect():
    import psycopg2

    url = database_url()
    try:
        return psycopg2.connect(url, connect_timeout=10)
    except psycopg2.OperationalError as exc:
        message = str(exc).strip().splitlines()[0]
        hint = ""
        if "password authentication failed" in message:
            hint = ("\nHint: the password inside DATABASE_URL does not match the PostgreSQL "
                    "role. Check .env (it must contain only ONE POSTGRES_PASSWORD line, equal "
                    "to the password in DATABASE_URL).")
        elif "does not exist" in message:
            hint = "\nHint: create the database first (see docs/person_a/setup_windows.md)."
        elif "Connection refused" in message or "could not connect" in message:
            hint = "\nHint: is PostgreSQL running and listening on that port?"
        sys.exit(f"Cannot connect to {safe_target(url)}: {message}{hint}")


def checksum(path: Path) -> str:
    # Normalise line endings so Windows checkouts give the same checksum.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def ensure_table(cur) -> None:
    cur.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version    TEXT PRIMARY KEY,
               checksum   TEXT NOT NULL,
               applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"""
    )


def applied(cur) -> dict[str, str]:
    cur.execute("SELECT version, checksum FROM schema_migrations")
    return dict(cur.fetchall())


def check() -> None:
    url = database_url()
    print(f"Target: {safe_target(url)}")
    conn = connect()
    with conn, conn.cursor() as cur:
        cur.execute("SHOW server_version")
        print("PostgreSQL:", cur.fetchone()[0])
        cur.execute("SELECT name, installed_version, default_version FROM pg_available_extensions "
                    "WHERE name IN ('postgis', 'pgrouting', 'btree_gist') ORDER BY name")
        for name, installed, default in cur.fetchall():
            print(f"  extension {name:10s} installed={installed or '-':8s} available={default}")
        cur.execute("SELECT to_regclass('public.' || t) IS NOT NULL FROM unnest(%s::text[]) t",
                    (EXPECTED_TABLES,))
        flags = [row[0] for row in cur.fetchall()]
        missing = [t for t, ok in zip(EXPECTED_TABLES, flags) if not ok]
        print("Tables present:", len(EXPECTED_TABLES) - len(missing), "/", len(EXPECTED_TABLES))
        if missing:
            print("  missing:", ", ".join(missing))
        if to_regclass(cur, "schema_migrations"):
            print("Applied migrations:", ", ".join(sorted(applied(cur))) or "(none)")
    conn.close()


def to_regclass(cur, name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{name}",))
    return cur.fetchone()[0]


def migrate(status_only: bool = False) -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    conn = connect()
    conn.autocommit = False
    with conn.cursor() as cur:
        ensure_table(cur)
        conn.commit()
        done = applied(cur)
        for path in files:
            version = path.stem
            digest = checksum(path)
            if version in done:
                state = "applied" if done[version] == digest else "applied (file changed since)"
                print(f"  {state:28s} {path.name}")
                continue
            if status_only:
                print(f"  {'PENDING':28s} {path.name}")
                continue
            print(f"  applying {path.name} ...", end=" ", flush=True)
            try:
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                    (version, digest),
                )
                conn.commit()
                print("ok")
            except Exception as exc:
                conn.rollback()
                print("FAILED")
                sys.exit(f"{path.name}: {str(exc).strip()}\n(rolled back; nothing from this file was applied)")
    conn.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="read-only environment check")
    parser.add_argument("--status", action="store_true", help="list migrations without applying")
    args = parser.parse_args(argv)
    if args.check:
        check()
    else:
        migrate(status_only=args.status)


if __name__ == "__main__":
    main()
