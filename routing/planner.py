"""End-to-end route planning: graph -> candidates -> relevant NOTAMs -> conflicts -> selection.

Used by ``POST /plan`` and the routing evaluation.  Research decision support
only; not for operational use.
"""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Optional

from api.relevance import DISCLAIMER, RetrievalError, UnknownAirport, validate_query
from routing.candidates import great_circle_nm, k_shortest_routes
from routing.conflicts import check_route, summarise
from routing.graph import DEFAULT_OFFSETS_NM, build_graph
from routing.select import select_route


def _airports(conn) -> dict:
    if conn is None:
        from db.reference_airports import reference_airports

        return reference_airports()
    from sqlalchemy import text

    rows = conn.execute(text(
        "SELECT icao_code, ST_Y(location) AS lat, ST_X(location) AS lon, fir_code FROM airport "
        "WHERE location IS NOT NULL")).mappings().all()
    return {r["icao_code"]: {"icao": r["icao_code"], "lat": r["lat"], "lon": r["lon"], "fir": r["fir_code"]}
            for r in rows}


def plan_route(src: str, dst: str, etd_utc, cruise_fl: int, *, tas_kt: float = 450.0,
               k: int = 10, corridor_nm: Optional[float] = None, connection=None,
               notam_features: Optional[list[dict]] = None, persist: bool = False,
               offsets_nm=DEFAULT_OFFSETS_NM) -> dict:
    """Plan a route.

    NOTAMs come from ``api.relevance.relevant_notams`` on ``connection``
    (PostGIS) unless ``notam_features`` is given (seed / test mode).
    """
    started = time.perf_counter()
    if not (0 < int(cruise_fl) <= 600):
        raise RetrievalError("cruise_fl must be between 1 and 600")
    if not (100 <= tas_kt <= 700):
        raise RetrievalError("tas_kt must be between 100 and 700")
    src, dst, etd, _, _, _, _ = validate_query(src, dst, etd_utc, None, 0, cruise_fl, corridor_nm or 200)
    airports = _airports(connection)
    if src not in airports or dst not in airports:
        raise UnknownAirport(f"{src} or {dst} not in airport table")
    s, d = {**airports[src], "icao": src}, {**airports[dst], "icao": dst}

    G = build_graph(s, d, connection, offsets_nm=offsets_nm)
    routes = k_shortest_routes(G, src, dst, k=k)
    gc_nm = great_circle_nm(s, d)
    longest = max(r.distance_nm for r in routes)
    eta_max = etd + timedelta(hours=longest / tas_kt)
    # The corridor must cover the widest candidate plus NOTAM radii.
    corridor = corridor_nm or max(200.0, max(abs(o) for o in offsets_nm) + 50.0)

    retrieval_meta = None
    if notam_features is None:
        from api.relevance import relevant_notams

        fc = relevant_notams(src, dst, etd, eta_max, 0, int(cruise_fl), corridor, connection=connection)
        notam_features, retrieval_meta = fc["features"], fc["metadata"]

    for r in routes:
        r.conflicts = check_route(r.points, notam_features, src=src, dst=dst, etd=etd,
                                  tas_kt=tas_kt, cruise_fl=int(cruise_fl))
    result = select_route(routes, etd=etd, tas_kt=tas_kt, gc_nm=gc_nm, cruise_fl=int(cruise_fl))
    result.update({
        "request": {"src": src, "dst": dst, "etd_utc": etd.isoformat().replace("+00:00", "Z"),
                    "cruise_fl": int(cruise_fl), "tas_kt": tas_kt, "k": k, "corridor_nm": corridor},
        "great_circle_nm": round(gc_nm, 1),
        "graph_source": G.graph.get("graph_source"),
        "graph_nodes": G.number_of_nodes(), "graph_edges": G.number_of_edges(),
        "relevant_notams": {"count": len(notam_features),
                            "features": notam_features, "retrieval": retrieval_meta},
        "conflict_counts_all_routes": summarise([c for r in routes for c in r.conflicts]),
        "runtime_ms": round((time.perf_counter() - started) * 1000, 1),
        "disclaimer": DISCLAIMER,
    })
    if G.graph.get("graph_source") == "synthetic_lattice":
        result["graph_note"] = ("Candidates use a synthetic lattice of laterally offset waypoints (ids SYN...), "
                                "not real ATS airways; load curated airway data into waypoint/airway_edge to "
                                "use the ATS graph.")
    if persist and connection is not None:
        result["request_id"] = persist_plan(connection, result, routes)
    return result


def persist_plan(conn, result: dict, routes) -> int:
    """Store the plan in route_request / candidate_route / route_conflict."""
    import json

    from sqlalchemy import text

    req = result["request"]
    request_id = conn.execute(text("""
        INSERT INTO route_request (origin_icao, dest_icao, etd_utc, cruise_fl, cruise_tas_kt)
        VALUES (:src, :dst, :etd, :fl, :tas) RETURNING request_id"""),
        {"src": req["src"], "dst": req["dst"], "etd": req["etd_utc"], "fl": req["cruise_fl"],
         "tas": int(req["tas_kt"])}).scalar()
    best_id = result["best_route"]["route_id"] if result.get("best_route") else None
    for r in routes:
        hard = [c for c in r.conflicts if c.conflict_type == "HARD"]
        route_db_id = conn.execute(text("""
            INSERT INTO candidate_route (request_id, total_dist_nm, est_time_min, is_feasible, is_selected,
                                         reject_reason, path)
            VALUES (:rid, :dist, :mins, :feasible, :selected, :reason,
                    ST_SetSRID(ST_GeomFromGeoJSON(:path), 4326))
            RETURNING route_id"""),
            {"rid": request_id, "dist": r.distance_nm, "mins": round(r.distance_nm / req["tas_kt"] * 60, 1),
             "feasible": not hard, "selected": r.route_id == best_id,
             "reason": "; ".join(c.explanation for c in hard) or None,
             "path": json.dumps(r.linestring())}).scalar()
        for c in r.conflicts:
            if c.conflict_type in ("HARD", "WARNING") and c.event_id is not None:
                conn.execute(text("""
                    INSERT INTO route_conflict (route_id, event_id, conflict_type, explanation)
                    VALUES (:route, :event, :kind, :why)"""),
                    {"route": route_db_id, "event": c.event_id, "kind": c.conflict_type, "why": c.explanation})
    return int(request_id)


__all__ = ["plan_route", "persist_plan"]
