"""Route selection (methodology layer 7).

* feasible = no HARD conflict
* best = shortest feasible route; ties (within 0.5 NM) broken by fewer warnings
* up to two alternatives
* AIRPORT_BLOCKING at source/destination -> status AIRPORT_UNAVAILABLE: the
  route list is still returned, but no route choice can fix it
* no feasible route -> status NO_FEASIBLE_ROUTE with all rejection reasons and
  concrete suggestions (cruise above/below the blocking band, or depart after
  it ends)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

WARNING_TYPES = ("WARNING", "UNLOCALISED")


def _count(route, kinds) -> int:
    return sum(1 for c in route.conflicts if c.conflict_type in kinds)


def route_summary(route, etd: datetime, tas_kt: float, gc_nm: float) -> dict:
    hard = [c for c in route.conflicts if c.conflict_type == "HARD"]
    return {
        "route_id": route.route_id,
        "nodes": route.nodes,
        "graph_source": route.graph_source,
        "is_direct": route.is_direct,
        "distance_nm": route.distance_nm,
        "extra_distance_nm": round(route.distance_nm - gc_nm, 1),
        "extra_distance_pct": round(100 * (route.distance_nm - gc_nm) / gc_nm, 2) if gc_nm else None,
        "est_time_min": round(route.distance_nm / tas_kt * 60, 1),
        "eta_utc": (etd + timedelta(hours=route.distance_nm / tas_kt)).isoformat().replace("+00:00", "Z"),
        "is_feasible": not hard,
        "hard_conflicts": len(hard),
        "warnings": _count(route, WARNING_TYPES),
        "reject_reason": "; ".join(c.explanation for c in hard) or None,
        "conflicts": [c.as_dict() for c in route.conflicts],
        "geometry": route.linestring(),
    }


def suggestions(routes, cruise_fl: int) -> list[str]:
    out = []
    seen = set()
    for r in routes:
        for c in r.conflicts:
            if c.conflict_type != "HARD" or c.notam_id in seen:
                continue
            seen.add(c.notam_id)
            out.append(f"{c.notam_id}: route blocked at {c.route_time_window[0]}-{c.route_time_window[1]} "
                       f"at FL{c.route_fl_range[0]:03d}-{c.route_fl_range[1]:03d}; try a cruise level outside "
                       "the NOTAM band or a departure time after the NOTAM ends")
    return out


def select_route(routes, *, etd: datetime, tas_kt: float, gc_nm: float, cruise_fl: int,
                 max_alternatives: int = 2) -> dict:
    airport = [c for c in (routes[0].conflicts if routes else []) if c.conflict_type == "AIRPORT_BLOCKING"]
    feasible = [r for r in routes if not any(c.conflict_type == "HARD" for c in r.conflicts)]
    feasible.sort(key=lambda r: (round(r.distance_nm / 0.5), _count(r, WARNING_TYPES), r.route_id))
    best: Optional[object] = feasible[0] if feasible else None
    alternatives = feasible[1:1 + max_alternatives]
    rejected = [r for r in routes if r not in feasible]

    if airport:
        status = "AIRPORT_UNAVAILABLE"
    elif best is None:
        status = "NO_FEASIBLE_ROUTE"
    else:
        status = "OK"

    def why_best(r) -> str:
        bits = [f"shortest feasible route ({r.distance_nm} NM, +{r.distance_nm - gc_nm:.1f} NM vs great circle)"]
        if rejected:
            shorter = [x for x in rejected if x.distance_nm < r.distance_nm]
            if shorter:
                bits.append(f"{len(shorter)} shorter candidate(s) rejected for HARD conflicts")
        bits.append(f"{_count(r, WARNING_TYPES)} warning(s)")
        return "; ".join(bits)

    return {
        "status": status,
        "best_route": route_summary(best, etd, tas_kt, gc_nm) if best else None,
        "why_best": why_best(best) if best else None,
        "alternatives": [route_summary(r, etd, tas_kt, gc_nm) for r in alternatives],
        "rejected_routes": [route_summary(r, etd, tas_kt, gc_nm) for r in rejected],
        "airport_blocking": [c.as_dict() for c in airport],
        "suggestions": suggestions(rejected, cruise_fl) if status == "NO_FEASIBLE_ROUTE" else [],
        "candidates_evaluated": len(routes),
        "feasible_count": len(feasible),
    }
