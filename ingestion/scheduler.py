"""Ingestion scheduler: fetch all configured sources, store raw, build events.

Owner: Person A.

    # one cycle from the saved local snapshots (no network) - first load / demo
    python -m ingestion.scheduler --once --offline

    # one live cycle (AAI PDFs + autorouter; FAA/ICAO when keys exist)
    python -m ingestion.scheduler --once

    # unattended polling every 15 minutes (Ctrl+C to stop)
    python -m ingestion.scheduler --loop --interval 15

Each adapter run is logged in ingestion_run (SUCCESS / PARTIAL / FAILED /
SKIPPED).  A failing source never stops the others.  Logs also go to
logs/ingestion.log.  On Windows, Task Scheduler can run ``--once`` every
15 minutes instead of ``--loop`` (see docs/person_a/setup_windows.md).
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from ingestion.base import SourceAdapter, SourceNotConfigured
from ingestion.store import StoreResult, ensure_source, finish_run, redact, start_run, store_raw

log = logging.getLogger("ingestion.scheduler")
ROOT = Path(__file__).resolve().parent.parent


def build_adapters(offline: bool, sources: list[str] | None = None) -> list[SourceAdapter]:
    from ingestion.aai import AaiAdapter
    from ingestion.autorouter import AutorouterAdapter
    from ingestion.faa import FaaAdapter
    from ingestion.icao import IcaoAdapter

    if offline:
        adapters = {
            "aai": AaiAdapter(offline_dir=ROOT / "data" / "raw"),
            "autorouter": AutorouterAdapter(offline_dir=ROOT / "data" / "autorouter"),
        }
    else:
        adapters = {
            "aai": AaiAdapter(),            # previous + current month, A-series
            "autorouter": AutorouterAdapter(),
            "faa": FaaAdapter(),
            "icao": IcaoAdapter(),
        }
    if sources:
        adapters = {k: v for k, v in adapters.items() if k in sources}
    return list(adapters.values())


def _minutes_since_success(conn, source_id: int) -> float | None:
    from sqlalchemy import text

    value = conn.execute(text("""
        SELECT EXTRACT(EPOCH FROM (now() - max(finished_at))) / 60.0
          FROM ingestion_run
         WHERE source_id = :sid AND status IN ('SUCCESS', 'PARTIAL')
    """), {"sid": source_id}).scalar()
    return float(value) if value is not None else None


def run_adapter(engine, adapter: SourceAdapter, trigger: str) -> dict:
    with engine.begin() as conn:
        source_id = ensure_source(conn, adapter)
        if adapter.min_interval_min:
            since = _minutes_since_success(conn, source_id)
            if since is not None and since < adapter.min_interval_min:
                return {"source": adapter.name, "status": "NOT_DUE",
                        "minutes_since_success": round(since, 1)}
        run_id = start_run(conn, source_id, trigger)

    if not adapter.is_configured():
        with engine.begin() as conn:
            finish_run(conn, run_id, "SKIPPED", error="source not configured")
        return {"source": adapter.name, "status": "SKIPPED"}

    try:
        records = adapter.fetch()
    except SourceNotConfigured as exc:
        with engine.begin() as conn:
            finish_run(conn, run_id, "SKIPPED", error=str(exc))
        return {"source": adapter.name, "status": "SKIPPED"}
    except Exception as exc:
        message = redact(f"{type(exc).__name__}: {exc}")
        log.error("%s fetch failed: %s", adapter.name, message)
        with engine.begin() as conn:
            finish_run(conn, run_id, "FAILED", error=message)
        return {"source": adapter.name, "status": "FAILED", "error": message}

    try:
        with engine.begin() as conn:
            result = store_raw(conn, run_id, records)
    except Exception as exc:
        message = redact(f"{type(exc).__name__}: {exc}")
        log.error("%s store failed: %s", adapter.name, message)
        with engine.begin() as conn:
            finish_run(conn, run_id, "FAILED", StoreResult(fetched=len(records)), message)
        return {"source": adapter.name, "status": "FAILED", "error": message}

    partial = getattr(adapter, "failures", None)
    status = "PARTIAL" if partial else "SUCCESS"
    with engine.begin() as conn:
        finish_run(conn, run_id, status, result,
                   "; ".join(partial)[:2000] if partial else None)
    summary = {"source": adapter.name, "status": status, **result.__dict__}
    log.info("%s", summary)
    return summary


def run_once(offline: bool = False, sources: list[str] | None = None,
             trigger: str = "manual") -> dict:
    from api.db import get_engine
    from ingestion.process import process_pending

    engine = get_engine()
    runs = [run_adapter(engine, a, trigger) for a in build_adapters(offline, sources)]
    with engine.begin() as conn:
        processed = process_pending(conn)
    summary = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "runs": runs, "processing": processed.__dict__}
    log.info("cycle done: %s", summary["processing"])
    return summary


def _setup_logging() -> None:
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(ROOT / "logs" / "ingestion.log", encoding="utf-8")],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="NOTAM ingestion scheduler")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="run one cycle and exit")
    mode.add_argument("--loop", action="store_true", help="run forever")
    mode.add_argument("--process-only", action="store_true",
                      help="only parse/classify pending raw rows")
    parser.add_argument("--offline", action="store_true",
                        help="use saved snapshots in data/raw and data/autorouter")
    parser.add_argument("--sources", nargs="+", choices=["aai", "autorouter", "faa", "icao"])
    parser.add_argument("--interval", type=float, default=15.0, help="minutes between cycles")
    parser.add_argument("--reprocess-failed", action="store_true")
    args = parser.parse_args(argv)
    _setup_logging()

    if args.process_only:
        from api.db import get_engine
        from ingestion.process import process_pending

        with get_engine().begin() as conn:
            print(process_pending(conn, reprocess_failed=args.reprocess_failed))
        return

    if args.once:
        summary = run_once(args.offline, args.sources)
        for run in summary["runs"]:
            print(run)
        print("processing:", summary["processing"])
        return

    while True:
        try:
            run_once(args.offline, args.sources, trigger="scheduler")
        except Exception as exc:  # e.g. database restarting
            log.error("cycle failed: %s", redact(str(exc)))
        time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
