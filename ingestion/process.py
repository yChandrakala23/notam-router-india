"""Turn pending raw_notam rows into structured notam_event rows.

Owner: Person A.

Pipeline per raw row::

    raw_text --parse--> ParsedNotam/AaiNotam --classify--> EventRecord --SQL--> notam_event

* Geometry is built **in PostGIS** exactly as the methodology specifies:
  ``ST_Buffer(ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography,
  radius_nm * 1852)::geometry``.
* AAI summary NOTAMs have no Q-line: if their aerodrome is in the ``airport``
  table they get a default 5 NM aerodrome circle (``geom_source =
  'AERODROME_DEFAULT'``); FIR-level entries become ``FIR_WIDE`` (no geometry).
* One event per NOTAM identity (issuing office + id).  When several sources
  describe the same NOTAM the higher ``source_rank`` (Q-line sources) wins;
  for equal rank the latest observation wins.
* Malformed NOTAMs never stop the run: the raw row is marked FAILED with the
  reason in ``raw_notam.parse_error``.
* After each batch ``resolve_notam_lifecycle()`` applies NOTAMR / NOTAMC.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional


from classification.merged import classify
from ingestion.base import INDIAN_FIRS, SOURCE_RANK
from parsing.aai_summary import REGION_NOF, parse_block
from parsing.autorouter_record import parse_autorouter_record
from parsing.qline import ParsedNotam, parse_notam


def text(sql: str):
    """Lazy SQLAlchemy ``text()`` so pure-Python parts import without SQLAlchemy."""
    from sqlalchemy import text as _text

    return _text(sql)

log = logging.getLogger("ingestion.process")

AERODROME_DEFAULT_RADIUS_NM = 5.0
NOTAM_ID = re.compile(r"^[A-Z]\d{4}/\d{2}$")
ICAO_CODE = re.compile(r"^[A-Z]{4}$")
_NOF_TO_FIR = {nof: fir for nof, fir in REGION_NOF.values()}


@dataclass
class EventRecord:
    notam_id: str
    nof: str
    series: Optional[str]
    notam_number: Optional[int]
    notam_year: Optional[int]
    action: str
    replaces_notam_id: Optional[str]
    fir_code: Optional[str]
    icao_location: Optional[str]
    q_code: Optional[str]
    traffic: Optional[str]
    purpose: Optional[str]
    scope: Optional[str]
    lower_fl: Optional[int]
    upper_fl: Optional[int]
    valid_from: datetime
    valid_until: Optional[datetime]
    is_permanent: bool
    end_estimated: bool
    schedule_text: Optional[str]
    e_text: Optional[str]
    center_lat: Optional[float]
    center_lon: Optional[float]
    radius_nm: Optional[float]
    geom_source: str
    category: str
    severity: str
    classifier_conf: float
    classifier_method: str
    source_rank: int
    classifier_reason: Optional[str] = None
    classifier_keyword: Optional[str] = None
    classifier_uncertainty: tuple = ()


class ParseFailure(ValueError):
    pass


def _from_icao(parsed: ParsedNotam, nof: Optional[str], raw_format: str, model) -> EventRecord:
    if parsed.errors:
        raise ParseFailure("; ".join(parsed.errors))
    if not parsed.notam_id or not NOTAM_ID.match(parsed.notam_id):
        raise ParseFailure("missing or malformed NOTAM id")
    q = parsed.qline
    location = parsed.icao_location
    fir = q.fir if q else None
    if not nof:
        # ICAO text from FAA/ICAO carries no issuing office.  Namespace the id
        # by FIR/location so equal ids from different offices never collide.
        nof = f"UNK-{fir or location or 'NA'}"

    lat = lon = radius = None
    if q and q.has_circle and not q.is_fir_wide:
        geom_source, lat, lon, radius = "QLINE_CIRCLE", q.latitude, q.longitude, q.radius_nm
        radius = max(radius, 1.0)  # radius 000 -> 1 NM minimum circle
    elif q and q.is_fir_wide:
        geom_source, radius = "FIR_WIDE", q.radius_nm
    elif location and location in INDIAN_FIRS:
        geom_source = "FIR_WIDE"
    elif location:
        geom_source = "AERODROME_DEFAULT"
        radius = AERODROME_DEFAULT_RADIUS_NM
    else:
        geom_source = "NONE"

    result = classify(q.q_code if q else None, parsed.e_text, model=model)
    return EventRecord(
        notam_id=parsed.notam_id, nof=nof or "", series=parsed.series,
        notam_number=parsed.number, notam_year=parsed.year,
        action=parsed.action or "N", replaces_notam_id=parsed.replaces_notam_id,
        fir_code=fir, icao_location=location,
        q_code=q.q_code if q else None, traffic=q.traffic if q else None,
        purpose=q.purpose if q else None, scope=q.scope if q else None,
        lower_fl=q.lower_fl if q else None, upper_fl=q.upper_fl if q else None,
        valid_from=parsed.valid_from, valid_until=parsed.valid_until,
        is_permanent=parsed.is_permanent, end_estimated=parsed.end_estimated,
        schedule_text=parsed.schedule, e_text=parsed.e_text,
        center_lat=lat, center_lon=lon, radius_nm=radius, geom_source=geom_source,
        category=result.category, severity=result.severity,
        classifier_conf=result.confidence, classifier_method=result.method,
        source_rank=SOURCE_RANK.get(raw_format, 0),
        classifier_reason=result.reason, classifier_keyword=result.keyword,
        classifier_uncertainty=tuple(result.uncertainty),
    )


def build_event(raw_format: str, raw_text: str, *, nof: Optional[str] = None,
                location_hint: Optional[str] = None, model="default") -> EventRecord:
    """Parse + classify one raw NOTAM.  Raises ParseFailure for malformed input."""
    if raw_format == "icao_text":
        return _from_icao(parse_notam(raw_text), nof, raw_format, model)
    if raw_format == "autorouter_json":
        import json

        try:
            record = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ParseFailure(f"invalid JSON: {exc}") from exc
        return _from_icao(parse_autorouter_record(record), record.get("nof") or nof,
                          raw_format, model)
    if raw_format == "aai_summary":
        fir = _NOF_TO_FIR.get(nof or "")
        parsed = parse_block(raw_text, nof=nof, fir_code=fir)
        if parsed.errors:
            raise ParseFailure("; ".join(parsed.errors))
        location = location_hint if location_hint and ICAO_CODE.match(location_hint) else None
        if location in INDIAN_FIRS:
            geom_source, radius, fir = "FIR_WIDE", None, location
        elif location:
            geom_source, radius = "AERODROME_DEFAULT", AERODROME_DEFAULT_RADIUS_NM
        else:
            geom_source, radius = "NONE", None
        result = classify(None, parsed.e_text, model=model)
        if geom_source == "AERODROME_DEFAULT" and result.category in ("NAV_WARNING", "AIRSPACE_RESTRICTION"):
            # e.g. SHAR rocket-launch NOTAMs listed under "CHENNAI VOMM": the
            # activity is not at the aerodrome, so do not draw an aerodrome
            # circle; keep it FIR-level (routing reports it as UNLOCALISED).
            geom_source, radius = "FIR_WIDE", None
        return EventRecord(
            notam_id=parsed.notam_id, nof=nof or "", series=parsed.series,
            notam_number=parsed.number, notam_year=parsed.year,
            action="N", replaces_notam_id=None,  # summaries list NOTAMs in force
            fir_code=fir, icao_location=location, q_code=None,
            traffic=None, purpose=None, scope=None, lower_fl=None, upper_fl=None,
            valid_from=parsed.valid_from, valid_until=parsed.valid_until,
            is_permanent=parsed.is_permanent, end_estimated=parsed.end_estimated,
            schedule_text=parsed.schedule, e_text=parsed.e_text,
            center_lat=None, center_lon=None, radius_nm=radius, geom_source=geom_source,
            category=result.category, severity=result.severity,
            classifier_conf=result.confidence, classifier_method=result.method,
            source_rank=SOURCE_RANK.get(raw_format, 0),
            classifier_reason=result.reason, classifier_keyword=result.keyword,
            classifier_uncertainty=tuple(result.uncertainty),
        )
    raise ParseFailure(f"unknown raw_format {raw_format!r}")


# --------------------------------------------------------------------------
# SQL
# --------------------------------------------------------------------------

_UPSERT_EVENT = """
INSERT INTO notam_event (
    raw_id, notam_id, nof, series, notam_number, notam_year, action, replaces_notam_id,
    fir_code, icao_location, q_code, traffic, purpose, scope, lower_fl, upper_fl,
    valid_during, center, geom, radius_nm, geom_source, is_permanent, end_estimated,
    schedule_text, e_text, category, severity, classifier_conf, classifier_method,
    source_rank, classifier_reason, classifier_keyword, classifier_uncertainty)
VALUES (
    :raw_id, :notam_id, :nof, :series, :notam_number, :notam_year, :action, :replaces_notam_id,
    :fir_code, :icao_location, :q_code, :traffic, :purpose, :scope, :lower_fl, :upper_fl,
    tstzrange(:valid_from, :valid_until, '[]'),
    CASE WHEN :geom_source = 'QLINE_CIRCLE'
         THEN ST_SetSRID(ST_MakePoint(:center_lon, :center_lat), 4326) END,
    CASE WHEN :geom_source = 'QLINE_CIRCLE'
         THEN ST_Buffer(ST_SetSRID(ST_MakePoint(:center_lon, :center_lat), 4326)::geography,
                        :radius_nm * 1852.0)::geometry
         WHEN :geom_source = 'AERODROME_DEFAULT'
         THEN (SELECT ST_Buffer(a.location::geography, :radius_nm * 1852.0)::geometry
                 FROM airport a
                WHERE a.icao_code = :icao_location AND a.location IS NOT NULL)
    END,
    :radius_nm, :geom_source, :is_permanent, :end_estimated,
    :schedule_text, :e_text, :category, :severity, :classifier_conf, :classifier_method,
    :source_rank, :classifier_reason, :classifier_keyword, :classifier_uncertainty)
ON CONFLICT ON CONSTRAINT notam_event_identity_uq DO UPDATE SET
    raw_id = EXCLUDED.raw_id, series = EXCLUDED.series,
    notam_number = EXCLUDED.notam_number, notam_year = EXCLUDED.notam_year,
    action = EXCLUDED.action, replaces_notam_id = EXCLUDED.replaces_notam_id,
    fir_code = EXCLUDED.fir_code, icao_location = EXCLUDED.icao_location,
    q_code = EXCLUDED.q_code, traffic = EXCLUDED.traffic, purpose = EXCLUDED.purpose,
    scope = EXCLUDED.scope, lower_fl = EXCLUDED.lower_fl, upper_fl = EXCLUDED.upper_fl,
    valid_during = EXCLUDED.valid_during, center = EXCLUDED.center, geom = EXCLUDED.geom,
    radius_nm = EXCLUDED.radius_nm, geom_source = EXCLUDED.geom_source,
    is_permanent = EXCLUDED.is_permanent, end_estimated = EXCLUDED.end_estimated,
    schedule_text = EXCLUDED.schedule_text, e_text = EXCLUDED.e_text,
    category = EXCLUDED.category, severity = EXCLUDED.severity,
    classifier_conf = EXCLUDED.classifier_conf, classifier_method = EXCLUDED.classifier_method,
    source_rank = EXCLUDED.source_rank, classifier_reason = EXCLUDED.classifier_reason,
    classifier_keyword = EXCLUDED.classifier_keyword,
    classifier_uncertainty = EXCLUDED.classifier_uncertainty
WHERE notam_event.source_rank < EXCLUDED.source_rank
   OR (notam_event.source_rank = EXCLUDED.source_rank AND notam_event.raw_id <= EXCLUDED.raw_id)
RETURNING event_id
"""

_ENSURE_FIR = "INSERT INTO fir (icao_code) VALUES (:fir) ON CONFLICT (icao_code) DO NOTHING"

_MARK_RAW = """
    UPDATE raw_notam SET parse_status = :status, parse_error = :error, parsed_at = now()
     WHERE raw_id = :raw_id
"""

_BACKFILL_AERODROME_GEOM = """
    UPDATE notam_event e
       SET geom = ST_Buffer(a.location::geography, COALESCE(e.radius_nm, 5) * 1852.0)::geometry
      FROM airport a
     WHERE e.geom IS NULL AND e.geom_source = 'AERODROME_DEFAULT'
       AND a.icao_code = e.icao_location AND a.location IS NOT NULL
"""


@dataclass
class ProcessResult:
    parsed: int = 0
    failed: int = 0
    events_written: int = 0
    skipped_lower_rank: int = 0
    lifecycle: dict | None = None
    aerodrome_geom_backfilled: int = 0


def process_pending(conn, *, limit: int | None = None, model="default",
                    reprocess_failed: bool = False) -> ProcessResult:
    """Parse/classify pending raw rows (in raw_id order) and upsert events."""
    statuses = "('PENDING', 'FAILED')" if reprocess_failed else "('PENDING')"
    rows = conn.execute(text(f"""
        SELECT raw_id, raw_format, raw_text, nof, location_hint
          FROM raw_notam WHERE parse_status IN {statuses}
         ORDER BY raw_id {'LIMIT :limit' if limit else ''}
    """), {"limit": limit} if limit else {}).all()

    result = ProcessResult()
    for raw_id, raw_format, raw_text, nof, location_hint in rows:
        try:
            event = build_event(raw_format, raw_text, nof=nof,
                                location_hint=location_hint, model=model)
        except ParseFailure as exc:
            result.failed += 1
            conn.execute(text(_MARK_RAW), {"status": "FAILED", "error": str(exc)[:1000], "raw_id": raw_id})
            log.warning("raw_id %s not parsed: %s", raw_id, exc)
            continue
        except Exception as exc:  # unexpected - log, keep going
            result.failed += 1
            conn.execute(text(_MARK_RAW), {"status": "FAILED",
                                     "error": f"unexpected: {type(exc).__name__}: {exc}"[:1000],
                                     "raw_id": raw_id})
            log.exception("raw_id %s crashed the parser", raw_id)
            continue

        params = asdict(event)
        params["raw_id"] = raw_id
        params["classifier_uncertainty"] = list(params["classifier_uncertainty"])
        if params["fir_code"] and ICAO_CODE.match(params["fir_code"]):
            conn.execute(text(_ENSURE_FIR), {"fir": params["fir_code"]})
        else:
            params["fir_code"] = None
        written = conn.execute(text(_UPSERT_EVENT), params).first()
        if written:
            result.events_written += 1
        else:
            result.skipped_lower_rank += 1
        result.parsed += 1
        conn.execute(text(_MARK_RAW), {"status": "PARSED", "error": None, "raw_id": raw_id})

    result.aerodrome_geom_backfilled = conn.execute(text(_BACKFILL_AERODROME_GEOM)).rowcount
    linked, replaced, cancelled = conn.execute(
        text("SELECT * FROM resolve_notam_lifecycle()")).one()
    result.lifecycle = {"linked": linked, "replaced": replaced, "cancelled": cancelled}
    return result
