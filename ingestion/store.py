"""Raw NOTAM storage: data_source, ingestion_run, idempotent raw_notam upsert.

Owner: Person A.

* ``raw_notam.content_hash`` is UNIQUE, so ``INSERT ... ON CONFLICT DO
  NOTHING`` makes re-fetching the same NOTAM a no-op (idempotent ingestion).
* Raw text is stored exactly as the adapter returned it.
* Every adapter execution is logged in ``ingestion_run`` with counts and a
  status (RUNNING -> SUCCESS / PARTIAL / FAILED / SKIPPED).
* Replacement / cancellation handling happens on the structured events
  (``resolve_notam_lifecycle()`` in SQL, called by ``ingestion.process``).

All functions take an SQLAlchemy ``Connection``; the caller owns the
transaction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


from ingestion.base import RawNotam, SourceAdapter

_SECRET_PATTERNS = [
    re.compile(r"(api_key=)[^&\s'\"]+", re.I),
    re.compile(r"(client_secret[\"']?\s*[:=]\s*[\"']?)[^&\s'\",}]+", re.I),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"']?)[^&\s'\",}]+", re.I),
    re.compile(r"(postgres(?:ql)?://[^:/\s]+:)[^@\s]+(@)", re.I),
]


def redact(message: str) -> str:
    """Remove credentials from an error message before it is logged/stored."""
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub(lambda m: m.group(1) + "***" + (m.group(2) if m.lastindex and m.lastindex > 1 else ""), message)
    return message[:2000]


def text(sql: str):
    """Lazy SQLAlchemy ``text()`` so pure-Python parts import without SQLAlchemy."""
    from sqlalchemy import text as _text

    return _text(sql)


@dataclass
class StoreResult:
    fetched: int = 0
    inserted: int = 0
    duplicates: int = 0
    failed: int = 0


def ensure_source(conn, adapter: SourceAdapter) -> int:
    row = conn.execute(
        text("""
            INSERT INTO data_source (name, access_type, active, base_url)
            VALUES (:name, :access_type, true, :base_url)
            ON CONFLICT (name) DO UPDATE
               SET access_type = EXCLUDED.access_type,
                   base_url    = EXCLUDED.base_url
            RETURNING source_id
        """),
        {"name": adapter.name, "access_type": adapter.access_type,
         "base_url": adapter.base_url},
    ).one()
    return int(row[0])


def start_run(conn, source_id: int, trigger: str = "manual") -> int:
    row = conn.execute(
        text("""
            INSERT INTO ingestion_run (source_id, started_at, status, trigger)
            VALUES (:source_id, now(), 'RUNNING', :trigger)
            RETURNING run_id
        """),
        {"source_id": source_id, "trigger": trigger},
    ).one()
    return int(row[0])


def finish_run(conn, run_id: int, status: str, result: StoreResult | None = None,
               error: str | None = None) -> None:
    result = result or StoreResult()
    conn.execute(
        text("""
            UPDATE ingestion_run
               SET finished_at = now(), status = :status,
                   records_fetched = :fetched, records_inserted = :inserted,
                   records_duplicate = :duplicates, records_failed = :failed,
                   error_message = :error
             WHERE run_id = :run_id
        """),
        {"run_id": run_id, "status": status, "fetched": result.fetched,
         "inserted": result.inserted, "duplicates": result.duplicates,
         "failed": result.failed, "error": redact(error) if error else None},
    )


_INSERT_RAW = """
    INSERT INTO raw_notam (run_id, notam_id, nof, raw_text, raw_format, source_url,
                           location_hint, fetched_at, content_hash)
    VALUES (:run_id, :notam_id, :nof, :raw_text, :raw_format, :source_url,
            :location_hint, :fetched_at, :content_hash)
    ON CONFLICT (content_hash) DO NOTHING
    RETURNING raw_id
"""


def store_raw(conn, run_id: int, records: Iterable[RawNotam]) -> StoreResult:
    """Insert raw NOTAMs; duplicates (same content_hash) are skipped."""
    result = StoreResult()
    for record in records:
        result.fetched += 1
        if not record.raw_text or not record.raw_text.strip():
            result.failed += 1
            continue
        row = conn.execute(text(_INSERT_RAW), {
            "run_id": run_id,
            "notam_id": record.notam_id,
            "nof": record.nof,
            "raw_text": record.raw_text,
            "raw_format": record.raw_format,
            "source_url": record.source_url,
            "location_hint": record.location_hint,
            "fetched_at": record.fetched_at,
            "content_hash": record.content_hash,
        }).first()
        if row is None:
            result.duplicates += 1
        else:
            result.inserted += 1
    return result
