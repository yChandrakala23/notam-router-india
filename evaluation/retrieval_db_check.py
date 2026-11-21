"""Check the PostGIS implementation against the Python reference, on the live DB.

Owner: Person A.   Run after ingestion:

    python -m evaluation.retrieval_db_check --etd 2026-11-05T06:00:00Z

1. Geometry validity of every stored NOTAM circle (valid, SRID 4326, Polygon,
   area close to pi*r^2).
2. For the five test corridors: SQL ``relevant_notams()`` vs
   ``relevant_notams_reference()`` on the same rows (airport positions and
   crossed FIRs read from the DB).  Differences are expected only for NOTAMs
   within ~0.5 % of the corridor edge (PostGIS uses the WGS-84 spheroid, the
   reference a sphere).
3. Query time per corridor (median of N runs, target < 500 ms).

Writes evaluation/results/retrieval_db_check.json / .md.
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from api.relevance import relevant_notams, relevant_notams_reference
from db.reference_airports import IATA_TO_ICAO_CORRIDORS, TEST_CORRIDORS

RESULTS = Path(__file__).resolve().parent / "results"

GEOMETRY_SQL = """
SELECT count(*)                                                        AS with_geom,
       count(*) FILTER (WHERE ST_IsValid(geom))                        AS valid,
       count(*) FILTER (WHERE ST_SRID(geom) = 4326)                    AS srid_4326,
       count(*) FILTER (WHERE GeometryType(geom) = 'POLYGON')          AS polygons,
       min(ST_Area(geom::geography) / (pi() * (radius_nm * 1852.0) ^ 2)) AS min_area_ratio,
       max(ST_Area(geom::geography) / (pi() * (radius_nm * 1852.0) ^ 2)) AS max_area_ratio
  FROM notam_event WHERE geom IS NOT NULL AND radius_nm > 0
"""

EVENTS_SQL = """
SELECT e.event_id, e.notam_id, e.nof, e.action, e.lifecycle_status,
       lower(e.valid_during) AS valid_from, upper(e.valid_during) AS valid_until,
       e.lower_fl, e.upper_fl, e.icao_location, e.fir_code, e.geom_source,
       ST_Y(e.center) AS center_lat, ST_X(e.center) AS center_lon, e.radius_nm::float AS radius_nm,
       e.severity, e.category, e.e_text,
       (e.geom IS NOT NULL) AS has_geom
  FROM notam_event e
"""

AIRPORTS_SQL = """
SELECT icao_code, ST_Y(location) AS lat, ST_X(location) AS lon, fir_code
  FROM airport WHERE location IS NOT NULL
"""

EDGE_SQL = """
SELECT e.event_id, ST_Distance(e.geom::geography, ST_MakeLine(s.location, d.location)::geography) / 1852.0
  FROM notam_event e, airport s, airport d
 WHERE s.icao_code = :src AND d.icao_code = :dst AND e.event_id = ANY(:ids) AND e.geom IS NOT NULL
"""

ROUTE_FIRS_SQL = """
SELECT f.icao_code FROM fir f, airport s, airport d
 WHERE s.icao_code = :src AND d.icao_code = :dst AND f.boundary IS NOT NULL
   AND ST_DWithin(f.boundary::geography, ST_MakeLine(s.location, d.location)::geography, :m)
"""


def main(argv=None):
    from sqlalchemy import text

    from api.db import get_engine

    parser = argparse.ArgumentParser(description="PostGIS retrieval check")
    parser.add_argument("--etd", default=datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat())
    parser.add_argument("--fl-hi", type=int, default=350)
    parser.add_argument("--corridor-nm", type=float, default=200.0)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)
    etd = datetime.fromisoformat(args.etd.replace("Z", "+00:00"))

    out = {"etd_utc": etd.isoformat(), "corridor_nm": args.corridor_nm, "fl_hi": args.fl_hi}
    with get_engine().connect() as conn:
        out["geometry"] = {k: (float(v) if v is not None else None)
                           for k, v in conn.execute(text(GEOMETRY_SQL)).mappings().one().items()}
        events = [dict(r) for r in conn.execute(text(EVENTS_SQL)).mappings().all()]
        for e in events:
            # AERODROME_DEFAULT rows without stored geometry are not spatial in SQL either
            if e["geom_source"] == "AERODROME_DEFAULT" and not e["has_geom"]:
                e["geom_source"] = "NONE"
        airports = {r["icao_code"]: {"lat": r["lat"], "lon": r["lon"], "fir": r["fir_code"]}
                    for r in conn.execute(text(AIRPORTS_SQL)).mappings().all()}
        rows = []
        for src_iata, dst_iata in TEST_CORRIDORS:
            src, dst = IATA_TO_ICAO_CORRIDORS[src_iata], IATA_TO_ICAO_CORRIDORS[dst_iata]
            if src not in airports or dst not in airports:
                rows.append({"corridor": f"{src_iata}-{dst_iata}", "error": "airport missing in DB"})
                continue
            times, sql_result = [], None
            for _ in range(args.runs + 1):
                sql_result = relevant_notams(src, dst, etd, None, 0, args.fl_hi, args.corridor_nm,
                                             connection=conn)
                times.append(sql_result["metadata"]["query_ms"])
            firs = {r[0] for r in conn.execute(text(ROUTE_FIRS_SQL),
                                               {"src": src, "dst": dst, "m": args.corridor_nm * 1852})}
            ref = relevant_notams_reference(events, src, dst, etd, sql_result["metadata"]["eta_utc"],
                                            0, args.fl_hi, args.corridor_nm,
                                            airports=airports, route_firs=firs)
            sql_ids = {f["properties"]["event_id"] for f in sql_result["features"]}
            ref_ids = {f["properties"]["event_id"] for f in ref["features"]}
            union = sql_ids | ref_ids
            diff = sorted(sql_ids ^ ref_ids)
            # Disagreements within 1 % of the corridor edge come from the
            # spheroid (PostGIS) vs sphere (reference) distance model.
            edge = set()
            if diff:
                for eid, dist in conn.execute(text(EDGE_SQL), {"src": src, "dst": dst, "ids": diff}):
                    if abs(float(dist) - args.corridor_nm) <= 0.01 * args.corridor_nm:
                        edge.add(eid)
            unexplained = set(diff) - edge
            rows.append({
                "corridor": f"{src_iata}-{dst_iata}",
                "sql_features": len(sql_ids), "reference_features": len(ref_ids),
                "agreement": round(len(sql_ids & ref_ids) / len(union), 4) if union else 1.0,
                "edge_cases_spheroid_vs_sphere": sorted(edge),
                "unexplained_differences": sorted(unexplained),
                "only_sql": sorted(sql_ids - ref_ids)[:20], "only_reference": sorted(ref_ids - sql_ids)[:20],
                "median_ms": round(statistics.median(times[1:]), 1), "max_ms": round(max(times[1:]), 1),
                "counts_by_severity": sql_result["metadata"]["counts_by_severity"],
            })
        out["corridors"] = rows

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "retrieval_db_check.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    lines = ["# PostGIS retrieval check (generated)", "", f"ETD {out['etd_utc']}", "",
             f"Geometry: {out['geometry']}", "",
             "| Corridor | SQL | reference | agreement | edge cases (<=1% of corridor) | unexplained | median ms | max ms | by severity |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['corridor']} | {r['error']} | | | | | | | |")
        else:
            lines.append(f"| {r['corridor']} | {r['sql_features']} | {r['reference_features']} | "
                         f"{r['agreement']:.1%} | {len(r['edge_cases_spheroid_vs_sphere'])} | "
                         f"{len(r['unexplained_differences'])} | {r['median_ms']} | {r['max_ms']} | "
                         f"{r['counts_by_severity']} |")
    (RESULTS / "retrieval_db_check.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
