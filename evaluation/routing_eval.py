"""Routing evaluation: feasibility, extra distance, runtime, conflict-check correctness.

    python -m evaluation.routing_eval --etd 2026-10-16T22:00:00Z      # needs the PostGIS DB
    python -m evaluation.routing_eval --synthetic-only                # no DB

Part A — real NOTAMs (database): the five test corridors at two cruise levels.
  Reports status, feasible candidates, best-route extra distance vs great
  circle, HARD rejections by cause, runtime.

Part B — designed conflict cases (SYNTHETIC NOTAMs, clearly labelled): each case
  has a known correct answer (reject / do not reject / airport unavailable).
  Measures correct rejections and false rejections of the conflict check.

Writes evaluation/results/routing_eval.{json,md}.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from db.reference_airports import IATA_TO_ICAO_CORRIDORS, TEST_CORRIDORS, reference_airports
from routing.geo import intermediate
from routing.planner import plan_route

RESULTS = Path(__file__).resolve().parent / "results"
SYN_ETD = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)


def _syn(eid, sev, lo, hi, lat, lon, r=40, start="2026-11-05T00:00:00Z", end="2026-11-06T00:00:00Z",
         reason="CORRIDOR", loc=None, category="AIRSPACE_RESTRICTION"):
    return {"type": "Feature", "id": eid, "geometry": None, "properties": {
        "event_id": eid, "notam_id": f"SYN{eid:03d}", "severity": sev, "category": category,
        "q_code": "QRTCA", "lower_fl": lo, "upper_fl": hi, "valid_during": {"start": start, "end": end},
        "radius_nm": r, "center_lat": lat, "center_lon": lon, "match_reason": reason, "icao_location": loc,
        "synthetic": True}}


def synthetic_cases() -> list[dict]:
    """Designed cases on DEL-BOM (SYNTHETIC NOTAMs; expected outcomes by construction)."""
    ap = reference_airports()
    s, d = ap["VIDP"], ap["VABB"]
    mlat, mlon = intermediate(s["lat"], s["lon"], d["lat"], d["lon"], 0.5)
    q1 = intermediate(s["lat"], s["lon"], d["lat"], d["lon"], 0.25)
    return [
        dict(name="blocking area on direct route, inside FL band", fl=200,
             features=[_syn(1, "BLOCKING", 0, 250, mlat, mlon)], expect_direct_rejected=True, expect_status="OK"),
        dict(name="same area, aircraft cruises above it", fl=350,
             features=[_syn(2, "BLOCKING", 0, 250, mlat, mlon)], expect_direct_rejected=False, expect_status="OK"),
        dict(name="same area, NOTAM expired before ETD", fl=200,
             features=[_syn(3, "BLOCKING", 0, 250, mlat, mlon, start="2026-11-04T00:00:00Z",
                            end="2026-11-04T12:00:00Z")], expect_direct_rejected=False, expect_status="OK"),
        dict(name="same area but RESTRICTIVE (warning only)", fl=200,
             features=[_syn(4, "RESTRICTIVE", 0, 250, mlat, mlon)], expect_direct_rejected=False, expect_status="OK"),
        dict(name="blocking area 300 NM off track", fl=200,
             features=[_syn(5, "BLOCKING", 0, 250, *intermediate(s["lat"], s["lon"], 13.0, 80.0, 0.5))],
             expect_direct_rejected=False, expect_status="OK"),
        dict(name="low-level area (SFC-FL050) on track at cruise distance from airports", fl=350,
             features=[_syn(6, "BLOCKING", 0, 50, mlat, mlon, r=20)], expect_direct_rejected=False, expect_status="OK"),
        dict(name="low-level area (SFC-FL050) on the climb-out 25% along track", fl=350,
             features=[_syn(7, "BLOCKING", 0, 50, q1[0], q1[1], r=10)], expect_direct_rejected=False, expect_status="OK"),
        dict(name="low-level area (SFC-FL100) 10 NM after departure", fl=350,
             features=[_syn(8, "BLOCKING", 0, 100, *intermediate(s["lat"], s["lon"], d["lat"], d["lon"], 10 / 614.6), r=5)],
             expect_direct_rejected=True, expect_status="NO_FEASIBLE_ROUTE_OR_OK"),
        dict(name="destination aerodrome closed", fl=350,
             features=[_syn(9, "BLOCKING", 0, 999, d["lat"], d["lon"], r=5, reason="AERODROME", loc="VABB",
                            category="AERODROME")],
             expect_direct_rejected=False, expect_status="AIRPORT_UNAVAILABLE"),
        dict(name="restricted area (Q-line circle) over the destination, all levels", fl=350,
             features=[_syn(11, "BLOCKING", 0, 999, d["lat"], d["lon"], r=15, reason="AERODROME", loc="VABB")],
             expect_direct_rejected=True, expect_status="NO_FEASIBLE_ROUTE"),
        dict(name="en-route aerodrome closed (overflight at FL350)", fl=350,
             features=[_syn(12, "BLOCKING", None, None, mlat, mlon, r=5, loc="VAAH", category="AERODROME")],
             expect_direct_rejected=False, expect_status="OK"),
        dict(name="wall across the corridor (r 250 NM), inside FL band", fl=200,
             features=[_syn(10, "BLOCKING", 0, 300, mlat, mlon, r=250)], expect_direct_rejected=True,
             expect_status="NO_FEASIBLE_ROUTE"),
    ]


def run_synthetic() -> dict:
    rows, correct = [], 0
    for case in synthetic_cases():
        r = plan_route("VIDP", "VABB", SYN_ETD, case["fl"], notam_features=case["features"])
        direct = next(x for x in (r["rejected_routes"] + ([r["best_route"]] if r["best_route"] else []) + r["alternatives"])
                      if x["is_direct"])
        rejected = not direct["is_feasible"]
        status_ok = (case["expect_status"] == r["status"] or
                     (case["expect_status"] == "NO_FEASIBLE_ROUTE_OR_OK" and r["status"] in ("OK", "NO_FEASIBLE_ROUTE")))
        ok = (rejected == case["expect_direct_rejected"]) and status_ok
        correct += ok
        rows.append({"case": case["name"], "cruise_fl": case["fl"], "status": r["status"],
                     "direct_rejected": rejected, "expected_direct_rejected": case["expect_direct_rejected"],
                     "expected_status": case["expect_status"], "correct": ok,
                     "best_extra_nm": r["best_route"]["extra_distance_nm"] if r["best_route"] else None,
                     "feasible": r["feasible_count"], "candidates": r["candidates_evaluated"],
                     "explanation": (direct["reject_reason"] or (direct["conflicts"][0]["explanation"]
                                                                  if direct["conflicts"] else "no conflict"))[:240]})
    should_reject = [x for x in rows if x["expected_direct_rejected"]]
    should_pass = [x for x in rows if not x["expected_direct_rejected"]]
    return {"cases": rows, "correct": correct, "total": len(rows),
            "correct_rejections": f"{sum(x['direct_rejected'] for x in should_reject)}/{len(should_reject)}",
            "false_rejections": f"{sum(x['direct_rejected'] for x in should_pass)}/{len(should_pass)}"}


def run_real(etd: datetime, levels=(350, 150), runs: int = 3) -> list[dict]:
    from api.db import get_engine

    out = []
    with get_engine().connect() as conn:
        for a, b in TEST_CORRIDORS:
            src, dst = IATA_TO_ICAO_CORRIDORS[a], IATA_TO_ICAO_CORRIDORS[b]
            for fl in levels:
                times, r = [], None
                for _ in range(runs):
                    t = time.perf_counter()
                    r = plan_route(src, dst, etd, fl, connection=conn)
                    times.append((time.perf_counter() - t) * 1000)
                hard_by_source = {}
                feats = {f["properties"]["event_id"]: f["properties"] for f in r["relevant_notams"]["features"]}
                for route in r["rejected_routes"]:
                    for c in route["conflicts"]:
                        if c["conflict_type"] == "HARD":
                            gs = feats.get(c["event_id"], {}).get("geom_source", "?")
                            hard_by_source[gs] = hard_by_source.get(gs, 0) + 1
                out.append({"corridor": f"{a}-{b}", "cruise_fl": fl, "status": r["status"],
                            "candidates": r["candidates_evaluated"], "feasible": r["feasible_count"],
                            "feasibility_rate": round(r["feasible_count"] / r["candidates_evaluated"], 3),
                            "great_circle_nm": r["great_circle_nm"],
                            "best_distance_nm": r["best_route"]["distance_nm"] if r["best_route"] else None,
                            "best_extra_pct": r["best_route"]["extra_distance_pct"] if r["best_route"] else None,
                            "best_warnings": r["best_route"]["warnings"] if r["best_route"] else None,
                            "relevant_notams": r["relevant_notams"]["count"],
                            "conflicts_all_routes": r["conflict_counts_all_routes"],
                            "hard_conflicts_by_geom_source": hard_by_source,
                            "airport_blocking": [c["notam_id"] for c in r["airport_blocking"]],
                            "median_ms": round(statistics.median(times), 1), "max_ms": round(max(times), 1)})
    return out


def to_markdown(res: dict) -> str:
    lines = ["# Routing evaluation (generated)", "", f"Generated: {res['generated_at']}", "",
             "Candidate graph: synthetic lateral-offset lattice (not real ATS airways) unless airway data is loaded.", ""]
    if res.get("real"):
        lines += [f"## A. Real NOTAMs from the database (ETD {res['etd_utc']})", "",
                  "| Corridor | FL | Status | feasible/cands | GC NM | best NM | extra % | warnings | relevant NOTAMs "
                  "| conflicts (all candidates) | HARD by geometry source | airport blocking | median ms |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in res["real"]:
            lines.append(f"| {r['corridor']} | {r['cruise_fl']} | {r['status']} | {r['feasible']}/{r['candidates']} | "
                         f"{r['great_circle_nm']} | {r['best_distance_nm']} | {r['best_extra_pct']} | {r['best_warnings']} | "
                         f"{r['relevant_notams']} | {r['conflicts_all_routes']} | {r['hard_conflicts_by_geom_source']} | "
                         f"{r['airport_blocking']} | {r['median_ms']} |")
        lines.append("")
    s = res["synthetic"]
    lines += ["## B. Designed conflict cases (SYNTHETIC NOTAMs, DEL-BOM)", "",
              f"Correct: {s['correct']}/{s['total']}; correct rejections {s['correct_rejections']}; "
              f"false rejections {s['false_rejections']}.", "",
              "| Case | FL | Status | direct rejected | expected | correct | best extra NM | explanation |",
              "|---|---|---|---|---|---|---|---|"]
    for c in s["cases"]:
        lines.append(f"| {c['case']} | {c['cruise_fl']} | {c['status']} | {c['direct_rejected']} | "
                     f"{c['expected_direct_rejected']} / {c['expected_status']} | {c['correct']} | {c['best_extra_nm']} | "
                     f"{c['explanation']} |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--etd", default="2026-10-16T22:00:00Z")
    ap.add_argument("--synthetic-only", action="store_true")
    args = ap.parse_args(argv)
    etd = datetime.fromisoformat(args.etd.replace("Z", "+00:00"))
    res = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "etd_utc": etd.isoformat(),
           "synthetic": run_synthetic()}
    if not args.synthetic_only:
        res["real"] = run_real(etd)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "routing_eval.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    (RESULTS / "routing_eval.md").write_text(to_markdown(res), encoding="utf-8")
    print(to_markdown(res))


if __name__ == "__main__":
    main()
