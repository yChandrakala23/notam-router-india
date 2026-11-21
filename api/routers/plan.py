"""POST /plan — NOTAM-aware route planning (routing side).

Body: {"src": "VIDP", "dst": "VABB", "etd": "2026-11-05T06:00:00Z", "fl": 350,
       "tas_kt": 450, "k": 10, "persist": false}

Returns the best feasible route, up to two alternatives, rejected routes with
readable reasons, aerodrome-level blocks, suggestions when nothing is
feasible, and the relevant NOTAMs used.  Research decision support only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.relevance import RetrievalError, UnknownAirport

log = logging.getLogger("api.plan")
router = APIRouter(tags=["routing"])


class PlanRequest(BaseModel):
    src: str = Field(..., min_length=4, max_length=4, examples=["VIDP"])
    dst: str = Field(..., min_length=4, max_length=4, examples=["VABB"])
    etd: datetime = Field(..., description="ETD with timezone, e.g. 2026-11-05T06:00:00Z")
    fl: int = Field(..., ge=1, le=600, description="cruise flight level")
    tas_kt: float = Field(450, ge=100, le=700)
    k: int = Field(10, ge=1, le=30, description="number of K-shortest candidates")
    corridor_nm: Optional[float] = Field(None, ge=1, le=500)
    persist: bool = Field(False, description="store request/candidates/conflicts in the DB")


@router.post("/plan")
def post_plan(body: PlanRequest):
    from api.db import get_engine
    from routing.planner import plan_route

    try:
        engine = get_engine()
        with engine.begin() as conn:
            return plan_route(body.src, body.dst, body.etd, body.fl, tas_kt=body.tas_kt, k=body.k,
                              corridor_nm=body.corridor_nm, connection=conn, persist=body.persist)
    except RetrievalError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnknownAirport as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        log.error("plan failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    except Exception as exc:
        if type(exc).__module__.startswith(("sqlalchemy", "psycopg2", "psycopg")):
            raise HTTPException(status_code=503, detail="database unavailable") from exc
        raise
