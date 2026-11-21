"""NOTAM endpoints owned by Person A.

GET /notams/relevant   relevant NOTAMs for a flight (GeoJSON FeatureCollection)
GET /notams/freshness  last successful fetch per data source

Example::

    GET /notams/relevant?src=VIDP&dst=VABB&etd=2026-11-05T06:00:00Z&fl_hi=350
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api import cache
from api.relevance import (DEFAULT_CORRIDOR_NM, DEFAULT_TAS_KT, RetrievalError,
                           UnknownAirport, relevant_notams)
from api.schemas import FreshnessResponse, RelevantNotamsResponse

log = logging.getLogger("api.notams")
router = APIRouter(prefix="/notams", tags=["notams (Person A)"])


def _db_unavailable(exc: Exception) -> HTTPException:
    log.error("database error: %s", type(exc).__name__)
    return HTTPException(status_code=503, detail="NOTAM database unavailable")


@router.get("/relevant", response_model=RelevantNotamsResponse)
def get_relevant_notams(
    src: str = Query(..., min_length=4, max_length=4, description="Source ICAO, e.g. VIDP"),
    dst: str = Query(..., min_length=4, max_length=4, description="Destination ICAO, e.g. VABB"),
    etd: datetime = Query(..., description="ETD, ISO-8601 with timezone, e.g. 2026-11-05T06:00:00Z"),
    eta: Optional[datetime] = Query(None, description="ETA; default ETD + distance / tas_kt"),
    fl_lo: int = Query(0, ge=0, le=999, description="Lowest flight level considered"),
    fl_hi: int = Query(..., ge=0, le=999, description="Highest flight level (cruise FL)"),
    corridor_nm: float = Query(DEFAULT_CORRIDOR_NM, ge=1, le=500,
                               description="Half-width of the route corridor in NM (150-300)"),
    tas_kt: float = Query(DEFAULT_TAS_KT, ge=100, le=700, description="Cruise TAS for ETA"),
    include_raw: bool = Query(False, description="Include raw NOTAM text in each feature"),
):
    params = dict(src=src.upper(), dst=dst.upper(), etd=etd.isoformat(),
                  eta=eta.isoformat() if eta else None, fl_lo=fl_lo, fl_hi=fl_hi,
                  corridor_nm=corridor_nm, tas_kt=tas_kt, include_raw=include_raw)
    try:
        from sqlalchemy import text

        from api.db import get_engine

        with get_engine().connect() as conn:
            version = conn.execute(text(cache.DATA_VERSION_SQL)).scalar() if cache.enabled() else None
            key = cache.make_key("relevant", params, version) if version else None
            if key and (hit := cache.get(key)) is not None:
                hit["metadata"]["cache"] = "hit"
                return hit
            result = relevant_notams(src, dst, etd, eta, fl_lo, fl_hi, corridor_nm,
                                     tas_kt=tas_kt, include_raw=include_raw, connection=conn)
            result["metadata"]["cache"] = "miss" if key else "disabled"
            if key:
                cache.set(key, result)
            return result
    except RetrievalError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnknownAirport as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except RuntimeError as exc:  # DATABASE_URL missing
        raise _db_unavailable(exc) from exc
    except Exception as exc:
        if type(exc).__module__.startswith(("sqlalchemy", "psycopg2")):
            raise _db_unavailable(exc) from exc
        raise


@router.get("/freshness", response_model=FreshnessResponse)
def get_freshness():
    try:
        from sqlalchemy import text

        from api.db import get_engine

        with get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT name, access_type, active, last_success_at, last_attempt_at, "
                "last_status, last_records_fetched, minutes_since_success, is_stale "
                "FROM v_source_freshness ORDER BY name")).mappings().all()
    except Exception as exc:
        raise _db_unavailable(exc) from exc
    sources = [dict(r) for r in rows]
    for s in sources:
        if s["minutes_since_success"] is not None:
            s["minutes_since_success"] = float(s["minutes_since_success"])
    active = [s for s in sources if s.get("active") is not False and s["last_status"] != "SKIPPED"]
    return {"sources": sources,
            "any_stale": any(s["is_stale"] for s in active) if active else True,
            "checked_at": datetime.now(timezone.utc)}
