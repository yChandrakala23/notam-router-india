"""Relevant-NOTAM retrieval (Person A -> Person B interface).

Owner: Person A.

Contract (docs/contract.md)::

    relevant_notams(src, dst, etd_utc, eta_utc, fl_lo, fl_hi, corridor_nm)
        -> GeoJSON FeatureCollection; each feature has properties
           severity, category, lower_fl, upper_fl, valid_during, e_text
           (+ ids, match_reason, distance_nm, ...) and geometry = geom.

A NOTAM is relevant when ALL of:
  1. it is ACTIVE (not replaced / cancelled) and is not itself a NOTAMC;
  2. its validity overlaps [ETD, ETA] (inclusive);
  3. EITHER it concerns the source/destination aerodrome (A) item)
     OR  its FL range overlaps [fl_lo, fl_hi] AND
         (its geometry lies within corridor_nm of the great-circle route,
          OR it is FIR-wide in a FIR touched by the corridor).

Changes vs. the methodology's sketch query (see docs/person_a/dbms_report.md):
  * ``ST_DWithin(geom::geography, route::geography, corridor_m)`` instead of
    buffering the route and testing distance 0 - same result, no buffer
    polygon to build, and it can use the GiST index on ``geom::geography``.
  * The FL test is not applied to source/destination aerodrome NOTAMs: the
    aircraft passes through every level from the surface to cruise there.
  * ``action <> 'C'`` became ``lifecycle_status = 'ACTIVE' AND action IS
    DISTINCT FROM 'C'`` so replaced/cancelled NOTAMs are excluded too.
  * NULL FL limits (sources without a Q-line) are unbounded -> conservative.

Research prototype - decision support only, not for operational use.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

DISCLAIMER = "Decision support for research only; not for operational use."
EARTH_RADIUS_NM = 3440.065
DEFAULT_CORRIDOR_NM = 200.0
DEFAULT_TAS_KT = 450.0
MAX_WINDOW = timedelta(hours=24)
SEVERITY_ORDER = {"BLOCKING": 0, "RESTRICTIVE": 1, "ADVISORY": 2}


class RetrievalError(ValueError):
    """Invalid query (HTTP 422)."""


class UnknownAirport(LookupError):
    """Source or destination not in the airport table (HTTP 404)."""


# --------------------------------------------------------------------------
# Validation and ETA
# --------------------------------------------------------------------------


def _as_utc(value: Any, name: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise RetrievalError(f"{name} is not an ISO-8601 datetime") from exc
    if not isinstance(value, datetime):
        raise RetrievalError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise RetrievalError(f"{name} must include a timezone (e.g. 2026-11-05T06:00Z)")
    return value.astimezone(timezone.utc)


def validate_query(src, dst, etd_utc, eta_utc, fl_lo, fl_hi, corridor_nm):
    import re

    src = (src or "").strip().upper()
    dst = (dst or "").strip().upper()
    for name, code in (("src", src), ("dst", dst)):
        if not re.fullmatch(r"V[AEIO][A-Z]{2}", code):
            raise RetrievalError(f"{name} must be an Indian ICAO aerodrome code (VA/VE/VI/VO**)")
    if src == dst:
        raise RetrievalError("src and dst must differ")
    etd = _as_utc(etd_utc, "etd")
    eta = _as_utc(eta_utc, "eta") if eta_utc is not None else None
    if eta is not None:
        if eta < etd:
            raise RetrievalError("eta must not precede etd")
        if eta - etd > MAX_WINDOW:
            raise RetrievalError("flight window longer than 24 h")
    try:
        fl_lo, fl_hi = int(fl_lo), int(fl_hi)
    except (TypeError, ValueError) as exc:
        raise RetrievalError("fl_lo / fl_hi must be integers (flight levels)") from exc
    if not (0 <= fl_lo <= fl_hi <= 999):
        raise RetrievalError("require 0 <= fl_lo <= fl_hi <= 999")
    corridor_nm = float(corridor_nm)
    if not (1 <= corridor_nm <= 500):
        raise RetrievalError("corridor_nm must be between 1 and 500 (methodology: 150-300)")
    return src, dst, etd, eta, fl_lo, fl_hi, corridor_nm


def estimate_eta(etd: datetime, distance_nm: float, tas_kt: float = DEFAULT_TAS_KT) -> datetime:
    """ETA = ETD + distance / cruise TAS (methodology layer 4)."""
    if tas_kt <= 0:
        raise RetrievalError("tas_kt must be positive")
    return etd + timedelta(hours=distance_nm / tas_kt)


# --------------------------------------------------------------------------
# Spherical geometry (reference implementation / seed mode)
# --------------------------------------------------------------------------


def gc_distance_nm(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_NM * math.asin(min(1.0, math.sqrt(a)))


def _bearing(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.atan2(y, x)


def point_to_arc_nm(lat, lon, a_lat, a_lon, b_lat, b_lon) -> float:
    """Distance from a point to the great-circle *segment* A-B."""
    d_ab = gc_distance_nm(a_lat, a_lon, b_lat, b_lon)
    d_ap = gc_distance_nm(a_lat, a_lon, lat, lon)
    if d_ab == 0:
        return d_ap
    delta13 = d_ap / EARTH_RADIUS_NM
    theta13 = _bearing(a_lat, a_lon, lat, lon)
    theta12 = _bearing(a_lat, a_lon, b_lat, b_lon)
    xt = math.asin(math.sin(delta13) * math.sin(theta13 - theta12))
    cos_xt = math.cos(xt)
    at = math.acos(max(-1.0, min(1.0, math.cos(delta13) / cos_xt))) if cos_xt else 0.0
    if math.cos(theta13 - theta12) < 0:
        at = -at
    at_nm = at * EARTH_RADIUS_NM
    if at_nm < 0:
        return d_ap
    if at_nm > d_ab:
        return gc_distance_nm(b_lat, b_lon, lat, lon)
    return abs(xt) * EARTH_RADIUS_NM


# --------------------------------------------------------------------------
# Feature formatting
# --------------------------------------------------------------------------


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def make_feature(row: dict, geometry: Optional[dict]) -> dict:
    distance = row.get("distance_nm")
    return {
        "type": "Feature",
        "id": row.get("event_id"),
        "geometry": geometry,
        "properties": {
            "event_id": row.get("event_id"),
            "notam_id": row.get("notam_id"),
            "nof": row.get("nof"),
            "action": row.get("action"),
            "severity": row.get("severity"),
            "category": row.get("category"),
            "q_code": row.get("q_code"),
            "icao_location": row.get("icao_location"),
            "fir_code": row.get("fir_code"),
            "lower_fl": row.get("lower_fl"),
            "upper_fl": row.get("upper_fl"),
            "valid_during": {
                "start": _iso(row.get("valid_from")),
                "end": _iso(row.get("valid_to")),        # null = PERM / open-ended
                "end_estimated": bool(row.get("end_estimated")),
                "permanent": bool(row.get("is_permanent")),
            },
            "radius_nm": float(row["radius_nm"]) if row.get("radius_nm") is not None else None,
            "geom_source": row.get("geom_source"),
            "match_reason": row.get("match_reason"),
            "distance_nm": round(float(distance), 1) if distance is not None else None,
            "e_text": row.get("e_text"),
            "schedule_text": row.get("schedule_text"),
            "classifier_conf": row.get("classifier_conf"),
            "classifier_method": row.get("classifier_method"),
            "classifier_reason": row.get("classifier_reason"),
            "classifier_keyword": row.get("classifier_keyword"),
            "classifier_uncertainty": list(row.get("classifier_uncertainty") or []),
            "center_lat": row.get("center_lat"),
            "center_lon": row.get("center_lon"),
            **({"raw_text": row["raw_text"]} if row.get("raw_text") is not None else {}),
        },
    }


def feature_collection(features: list[dict], meta: dict) -> dict:
    counts = {"BLOCKING": 0, "RESTRICTIVE": 0, "ADVISORY": 0}
    for f in features:
        sev = f["properties"].get("severity")
        if sev in counts:
            counts[sev] += 1
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {**meta, "count": len(features), "counts_by_severity": counts,
                     "generated_at": _iso(datetime.now(timezone.utc)),
                     "disclaimer": DISCLAIMER},
    }


# --------------------------------------------------------------------------
# PostGIS implementation (production path)
# --------------------------------------------------------------------------

ROUTE_SQL = """
SELECT s.icao_code AS src, d.icao_code AS dst,
       ST_Distance(s.location::geography, d.location::geography) / 1852.0 AS distance_nm
  FROM airport s, airport d
 WHERE s.icao_code = :src AND d.icao_code = :dst
   AND s.location IS NOT NULL AND d.location IS NOT NULL
"""

RELEVANT_SQL = """
WITH params AS (
    SELECT tstzrange(CAST(:etd AS timestamptz), CAST(:eta AS timestamptz), '[]') AS win,
           int4range(CAST(:fl_lo AS int), CAST(:fl_hi AS int), '[]')            AS fl,
           CAST(:corridor_nm AS float8) * 1852.0                                AS corridor_m
),
route AS (
    SELECT ST_MakeLine(s.location, d.location)::geography AS gc,
           s.fir_code AS src_fir, d.fir_code AS dst_fir
      FROM airport s, airport d
     WHERE s.icao_code = :src AND d.icao_code = :dst
),
route_firs AS (
    SELECT f.icao_code FROM fir f, route r, params p
     WHERE f.boundary IS NOT NULL AND ST_DWithin(f.boundary::geography, r.gc, p.corridor_m)
    UNION SELECT src_fir FROM route WHERE src_fir IS NOT NULL
    UNION SELECT dst_fir FROM route WHERE dst_fir IS NOT NULL
)
SELECT n.event_id, n.notam_id, n.nof, n.action, n.severity, n.category, n.q_code,
       n.icao_location, n.fir_code, n.lower_fl, n.upper_fl,
       lower(n.valid_during) AS valid_from, upper(n.valid_during) AS valid_to,
       n.is_permanent, n.end_estimated, n.radius_nm, n.geom_source,
       n.e_text, n.schedule_text, n.classifier_conf, n.classifier_method,
       n.classifier_reason, n.classifier_keyword, n.classifier_uncertainty,
       ST_Y(COALESCE(n.center, ST_Centroid(n.geom))) AS center_lat,
       ST_X(COALESCE(n.center, ST_Centroid(n.geom))) AS center_lon,
       ST_AsGeoJSON(n.geom, 6) AS geometry,
       CASE WHEN n.icao_location IN (:src, :dst) THEN 'AERODROME'
            WHEN n.geom IS NOT NULL THEN 'CORRIDOR'
            ELSE 'FIR_WIDE' END AS match_reason,
       CASE WHEN n.geom IS NOT NULL THEN ST_Distance(n.geom::geography, r.gc) / 1852.0 END AS distance_nm,
       CASE WHEN CAST(:include_raw AS boolean) THEN rn.raw_text END AS raw_text,
       rn.raw_format
  FROM notam_event n
  CROSS JOIN route r
  CROSS JOIN params p
  JOIN raw_notam rn ON rn.raw_id = n.raw_id
 WHERE n.lifecycle_status = 'ACTIVE'
   AND n.action IS DISTINCT FROM 'C'
   AND n.valid_during && p.win
   AND (    n.icao_location IN (:src, :dst)
        OR (    n.fl_range && p.fl
            AND (   (n.geom IS NOT NULL AND ST_DWithin(n.geom::geography, r.gc, p.corridor_m))
                 OR (n.geom IS NULL AND n.geom_source = 'FIR_WIDE'
                     AND n.fir_code IN (SELECT icao_code FROM route_firs)))))
 ORDER BY CASE n.severity WHEN 'BLOCKING' THEN 0 WHEN 'RESTRICTIVE' THEN 1 ELSE 2 END,
          distance_nm NULLS LAST, n.event_id
"""


def _raw_for_display(row: dict) -> Optional[str]:
    """Raw text for the UI; autorouter JSON is shown as rendered ICAO text."""
    raw = row.get("raw_text")
    if raw is None:
        return None
    if row.get("raw_format") == "autorouter_json":
        from parsing.autorouter_record import render_icao_text

        try:
            return render_icao_text(json.loads(raw))
        except (ValueError, TypeError):
            return None
    return raw


def relevant_notams(
    src: str,
    dst: str,
    etd_utc: datetime | str,
    eta_utc: datetime | str | None = None,
    fl_lo: int = 0,
    fl_hi: int = 999,
    corridor_nm: float = DEFAULT_CORRIDOR_NM,
    *,
    tas_kt: float = DEFAULT_TAS_KT,
    include_raw: bool = False,
    connection=None,
) -> dict:
    """Relevant NOTAMs as a GeoJSON FeatureCollection (PostGIS).

    ``eta_utc=None`` -> ETA = ETD + great-circle distance / ``tas_kt``.
    ``connection``: an SQLAlchemy Connection (Person B may pass its own);
    when omitted a pooled connection from ``api.db`` is used.
    """
    from sqlalchemy import text

    src, dst, etd, eta, fl_lo, fl_hi, corridor_nm = validate_query(
        src, dst, etd_utc, eta_utc, fl_lo, fl_hi, corridor_nm)

    def _run(conn):
        started = time.perf_counter()
        route = conn.execute(text(ROUTE_SQL), {"src": src, "dst": dst}).mappings().first()
        if route is None:
            raise UnknownAirport(f"{src} or {dst} not found in airport table (with location)")
        distance = float(route["distance_nm"])
        eta_final = eta or estimate_eta(etd, distance, tas_kt)
        rows = conn.execute(text(RELEVANT_SQL), {
            "src": src, "dst": dst, "etd": etd, "eta": eta_final,
            "fl_lo": fl_lo, "fl_hi": fl_hi, "corridor_nm": corridor_nm,
            "include_raw": include_raw,
        }).mappings().all()
        features = []
        for row in rows:
            row = dict(row)
            geometry = json.loads(row["geometry"]) if row.get("geometry") else None
            row["raw_text"] = _raw_for_display(row) if include_raw else None
            features.append(make_feature(row, geometry))
        meta = {
            "src": src, "dst": dst, "etd_utc": _iso(etd), "eta_utc": _iso(eta_final),
            "eta_estimated": eta is None, "tas_kt": tas_kt if eta is None else None,
            "route_distance_nm": round(distance, 1), "fl_lo": fl_lo, "fl_hi": fl_hi,
            "corridor_nm": corridor_nm, "engine": "postgis",
            "query_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        return feature_collection(features, meta)

    if connection is not None:
        return _run(connection)
    from api.db import get_engine

    with get_engine().connect() as conn:
        return _run(conn)


# --------------------------------------------------------------------------
# Pure-Python reference implementation (no database)
#   * seed mode for Person B (tests without PostGIS)
#   * offline evaluation; also used to cross-check the SQL results
# --------------------------------------------------------------------------


def _parse_dt(value) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def relevant_notams_reference(
    events: Iterable[dict],
    src: str, dst: str, etd_utc, eta_utc=None, fl_lo: int = 0, fl_hi: int = 999,
    corridor_nm: float = DEFAULT_CORRIDOR_NM, *, tas_kt: float = DEFAULT_TAS_KT,
    airports: Optional[dict] = None, route_firs: Optional[set] = None,
) -> dict:
    """Same semantics as RELEVANT_SQL on in-memory event dicts.

    Event dict keys (as produced by ingestion.process.EventRecord + ids):
    notam_id, nof, action, lifecycle_status (default ACTIVE), valid_from,
    valid_until, lower_fl, upper_fl, icao_location, fir_code, geom_source,
    center_lat, center_lon, radius_nm, severity, category, e_text, ...

    Circles are evaluated exactly on a sphere (distance from the circle to the
    great-circle segment).  PostGIS uses the WGS-84 spheroid; differences are
    below ~0.5 %.
    """
    from db.reference_airports import reference_airports
    from parsing.qline import circle_polygon

    src, dst, etd, eta, fl_lo, fl_hi, corridor_nm = validate_query(
        src, dst, etd_utc, eta_utc, fl_lo, fl_hi, corridor_nm)
    airports = airports or reference_airports()
    if src not in airports or dst not in airports:
        raise UnknownAirport(f"{src} or {dst} has no reference position")
    s, d = airports[src], airports[dst]
    distance = gc_distance_nm(s["lat"], s["lon"], d["lat"], d["lon"])
    eta_final = eta or estimate_eta(etd, distance, tas_kt)
    firs = set(route_firs or ()) | {s.get("fir"), d.get("fir")}

    started = time.perf_counter()
    rows = []
    for e in events:
        if (e.get("lifecycle_status") or "ACTIVE") != "ACTIVE" or e.get("action") == "C":
            continue
        start = _parse_dt(e.get("valid_from"))
        end = _parse_dt(e.get("valid_until") if "valid_until" in e else e.get("valid_to"))
        if start is None or start > eta_final or (end is not None and end < etd):
            continue

        lat, lon, radius = e.get("center_lat"), e.get("center_lon"), e.get("radius_nm")
        if e.get("geom_source") == "AERODROME_DEFAULT" and e.get("icao_location") in airports:
            ap = airports[e["icao_location"]]
            lat, lon = ap["lat"], ap["lon"]
        has_geom = e.get("geom_source") in ("QLINE_CIRCLE", "AERODROME_DEFAULT") and \
            lat is not None and lon is not None and radius
        dist = None
        if has_geom:
            dist = max(0.0, point_to_arc_nm(lat, lon, s["lat"], s["lon"], d["lat"], d["lon"]) - float(radius))

        lo = e.get("lower_fl")
        hi = e.get("upper_fl")
        fl_ok = (lo is None or lo <= fl_hi) and (hi is None or hi >= fl_lo)
        at_aerodrome = e.get("icao_location") in (src, dst)

        if at_aerodrome:
            reason = "AERODROME"
        elif fl_ok and has_geom and dist <= corridor_nm:
            reason = "CORRIDOR"
        elif fl_ok and not has_geom and e.get("geom_source") == "FIR_WIDE" and e.get("fir_code") in firs:
            reason = "FIR_WIDE"
        else:
            continue
        row = dict(e)
        row.update(valid_from=start, valid_to=end, match_reason=reason, distance_nm=dist,
                   center_lat=lat if has_geom else None, center_lon=lon if has_geom else None)
        geometry = circle_polygon(lat, lon, float(radius)) if has_geom else None
        rows.append((row, geometry))

    rows.sort(key=lambda rg: (SEVERITY_ORDER.get(rg[0].get("severity"), 3),
                              rg[0]["distance_nm"] if rg[0]["distance_nm"] is not None else 1e9,
                              str(rg[0].get("notam_id"))))
    features = [make_feature(r, g) for r, g in rows]
    meta = {"src": src, "dst": dst, "etd_utc": _iso(etd), "eta_utc": _iso(eta_final),
            "eta_estimated": eta is None, "tas_kt": tas_kt if eta is None else None,
            "route_distance_nm": round(distance, 1), "fl_lo": fl_lo, "fl_hi": fl_hi,
            "corridor_nm": corridor_nm, "engine": "python-reference",
            "query_ms": round((time.perf_counter() - started) * 1000, 1)}
    return feature_collection(features, meta)


def relevant_notams_from_file(path, *args, **kwargs) -> dict:
    """Seed mode: run the reference retrieval on a JSON list of event dicts."""
    with open(path, encoding="utf-8") as handle:
        events = json.load(handle)
    if isinstance(events, dict):
        events = events.get("events", [])
    return relevant_notams_reference(events, *args, **kwargs)


# --------------------------------------------------------------------------
# Legacy in-memory filter (kept for backwards compatibility with earlier tests)
# --------------------------------------------------------------------------


def _parse_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if result.tzinfo is None:
        return None
    return result.astimezone(timezone.utc)


def filter_relevant_notams(candidates, *, etd_utc, eta_utc, fl_lo, fl_hi, corridor_nm) -> dict:
    """Filter pre-computed spatial candidates (autorouter-normalised dicts).

    Superseded by :func:`relevant_notams` (PostGIS) and
    :func:`relevant_notams_reference`; kept because earlier tooling uses it.
    Candidates need lifecycle_status == 'current_candidate', start/end
    validity, lower/upper_fl_source, distance_nm and a GeoJSON geom.
    """
    etd, eta = _parse_utc(etd_utc), _parse_utc(eta_utc)
    if etd is None or eta is None:
        raise ValueError("ETD and ETA must be timezone-aware datetimes")
    if eta < etd:
        raise ValueError("ETA must not be earlier than ETD")
    if fl_lo > fl_hi:
        raise ValueError("fl_lo must not exceed fl_hi")
    if corridor_nm < 0:
        raise ValueError("corridor_nm cannot be negative")

    features = []
    for notam in candidates:
        if notam.get("lifecycle_status") != "current_candidate":
            continue
        start = _parse_utc(notam.get("start_validity_utc"))
        end_raw = notam.get("end_validity_utc")
        end = _parse_utc(end_raw)
        if start is None or (end_raw is not None and end is None) or (end and end < start):
            continue
        if not (start <= eta and (end is None or end >= etd)):
            continue
        try:
            lower = float(notam["lower_fl_source"]) if notam.get("lower_fl_source") is not None else -math.inf
            upper = float(notam["upper_fl_source"]) if notam.get("upper_fl_source") is not None else math.inf
        except (TypeError, ValueError):
            continue
        if lower > upper or not (lower <= fl_hi and upper >= fl_lo):
            continue
        try:
            distance = float(notam.get("distance_nm"))
        except (TypeError, ValueError):
            continue
        if distance < 0 or distance > corridor_nm or not isinstance(notam.get("geom"), dict):
            continue
        features.append({
            "type": "Feature",
            "geometry": notam["geom"],
            "properties": {
                "source_id": notam.get("source_id"),
                "severity": notam.get("severity"),
                "category": notam.get("category"),
                "lower_fl": notam.get("lower_fl_source"),
                "upper_fl": notam.get("upper_fl_source"),
                "valid_during": {"start": notam.get("start_validity_utc"),
                                 "end": notam.get("end_validity_utc")},
                "distance_nm": distance,
                "e_text": notam.get("item_e"),
            },
        })
    return {"type": "FeatureCollection", "features": features}
