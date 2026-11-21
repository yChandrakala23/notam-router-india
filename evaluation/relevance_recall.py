"""Relevance-retrieval evaluation: recall / precision vs autorouter, runtime.

Owner: Person A.

    python -m evaluation.relevance_recall                 # offline (no DB), AAI vs autorouter
    python -m evaluation.relevance_recall --db --runs 5   # also time the PostGIS query

Reference ("ground truth")
--------------------------
The autorouter snapshot in data/autorouter/ was fetched per aerodrome
(Item A = VIDP, VABB, VOBL, VOMM, VECC, VOHY; VISR when re-fetched).  For a
corridor SRC-DST the reference set is every autorouter NOTAM whose Item A is
SRC or DST, that is not a NOTAMC, not replaced/cancelled inside the snapshot,
and whose validity overlaps the flight window.  This is the aerodrome part of
an autorouter briefing; autorouter's en-route (FIR) briefing is not in the
snapshot, so en-route recall cannot be measured with this data.

System under test
-----------------
Retrieval over events built **only from the AAI summaries** (an independent
source), using the same parser, classifier and relevance rules as production
(pure-Python reference engine; ``--db`` additionally times the SQL engine).
NOTAMs are matched by identity (issuing office + NOTAM id).

Recall is split into
* data coverage  - is the reference NOTAM present in the AAI data at all?
                   (AAI summaries are monthly snapshots; NOTAMs issued after
                   the summary date cannot be there)
* algorithmic    - of the reference NOTAMs present in the AAI data, how many
                   did retrieval return?
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.relevance import relevant_notams_reference
from db.reference_airports import IATA_TO_ICAO_CORRIDORS, TEST_CORRIDORS
from ingestion.aai import AaiAdapter
from ingestion.notam_lifecycle import resolve_notam_lifecycle
from ingestion.process import ParseFailure, build_event

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evaluation" / "results"
OPEN = 2147483647
# autorouter snapshot files were written 2026-10-17 03:37 IST = 2026-10-16 22:07 UTC
DEFAULT_ETD = "2026-10-16T22:00:00+00:00"


def load_autorouter() -> list[dict]:
    rows = []
    for path in sorted((ROOT / "data" / "autorouter").glob("*_notams.jsonl")):
        with path.open(encoding="utf-8") as handle:
            rows += [json.loads(line) for line in handle if line.strip()]
    return rows


def ident(nof, series, number, year) -> str:
    return f"{nof}|{series}{int(number):04d}/{int(year) % 100:02d}"


def reference_sets(records, etd, eta) -> dict[str, set[str]]:
    """Reference NOTAM identities per aerodrome (Item A)."""
    lifecycle = resolve_notam_lifecycle(records, as_of=etd)
    out = defaultdict(set)
    for record, life in zip(records, lifecycle):
        if (record.get("type") or "").upper() == "C" or life["superseded_by"] or life["cancelled_by"]:
            continue
        start = datetime.fromtimestamp(record["startvalidity"], tz=timezone.utc)
        end_raw = record.get("endvalidity")
        end = None if end_raw in (None, OPEN) else datetime.fromtimestamp(end_raw, tz=timezone.utc)
        if start > eta or (end is not None and end < etd):
            continue
        for item_a in record.get("itema") or []:
            out[item_a].add(ident(record["nof"], record["series"], record["number"], record["year"]))
    return out


def aai_events(model="default") -> tuple[list[dict], dict]:
    raws = AaiAdapter.fetch_offline(ROOT / "data" / "raw")
    events, months = {}, defaultdict(set)
    for raw in raws:
        month = (raw.source_url or "").rsplit("_", 2)[-2:]
        if raw.nof and len(month) == 2:
            months[raw.nof].add("-".join(month).replace(".pdf", ""))
        try:
            event = build_event(raw.raw_format, raw.raw_text, nof=raw.nof,
                                location_hint=raw.location_hint, model=model)
        except ParseFailure:
            continue
        events[f"{event.nof}|{event.notam_id}"] = {**asdict(event), "action": "N"}
    for key, e in events.items():
        e["event_id"] = key
    return list(events.values()), {k: sorted(v) for k, v in months.items()}


def evaluate(etd: datetime, corridor_nm: float, fl_hi: int, model="default") -> dict:
    records = load_autorouter()
    events, aai_months = aai_events(model)
    aai_ids = {e["event_id"] for e in events}
    rows, totals = [], Counter()
    for src_iata, dst_iata in TEST_CORRIDORS:
        src, dst = IATA_TO_ICAO_CORRIDORS[src_iata], IATA_TO_ICAO_CORRIDORS[dst_iata]
        result = relevant_notams_reference(events, src, dst, etd, None, 0, fl_hi, corridor_nm)
        eta = datetime.fromisoformat(result["metadata"]["eta_utc"].replace("Z", "+00:00"))
        ref_by_ad = reference_sets(records, etd, eta)
        covered_ads = [a for a in (src, dst) if any(a in (r.get("itema") or []) for r in records)]
        reference = set().union(*(ref_by_ad.get(a, set()) for a in covered_ads)) if covered_ads else set()
        predicted = {f["properties"]["event_id"] for f in result["features"]}
        predicted_ad = {f["properties"]["event_id"] for f in result["features"]
                        if f["properties"]["match_reason"] == "AERODROME"
                        and f["properties"]["icao_location"] in covered_ads}
        available = reference & aai_ids
        hit = reference & predicted
        row = {
            "corridor": f"{src_iata}-{dst_iata}", "src": src, "dst": dst,
            "aerodromes_with_reference": covered_ads,
            "eta_utc": result["metadata"]["eta_utc"],
            "reference": len(reference),
            "in_aai_data": len(available),
            "retrieved_total": len(predicted),
            "retrieved_by_reason": dict(Counter(f["properties"]["match_reason"] for f in result["features"])),
            "retrieved_aerodrome_level": len(predicted_ad),
            "true_positives": len(hit),
            "recall_end_to_end": round(len(hit) / len(reference), 4) if reference else None,
            "recall_algorithmic": round(len(available & predicted) / len(available), 4) if available else None,
            "precision_aerodrome_level": round(len(predicted_ad & reference) / len(predicted_ad), 4) if predicted_ad else None,
            "missed_not_in_aai": sorted(reference - aai_ids)[:30],
            "missed_algorithmic": sorted(available - predicted),
            "query_ms_reference_engine": result["metadata"]["query_ms"],
        }
        rows.append(row)
        for k in ("reference", "in_aai_data", "true_positives", "retrieved_aerodrome_level"):
            totals[k] += row[k]
        totals["aerodrome_tp"] += len(predicted_ad & reference)
        totals["algorithmic_hits"] += len(available & predicted)
    summary = {
        "recall_end_to_end": round(totals["true_positives"] / totals["reference"], 4) if totals["reference"] else None,
        "data_coverage": round(totals["in_aai_data"] / totals["reference"], 4) if totals["reference"] else None,
        "recall_algorithmic": round(totals["algorithmic_hits"] / totals["in_aai_data"], 4) if totals["in_aai_data"] else None,
        "precision_aerodrome_level": round(totals["aerodrome_tp"] / totals["retrieved_aerodrome_level"], 4)
        if totals["retrieved_aerodrome_level"] else None,
        **{k: v for k, v in totals.items()},
    }
    return {"etd_utc": etd.isoformat(), "corridor_nm": corridor_nm, "fl_hi": fl_hi,
            "aai_summary_months_by_nof": aai_months, "autorouter_records": len(records),
            "aai_events": len(events), "corridors": rows, "summary": summary}


def time_db(etd: datetime, corridor_nm: float, fl_hi: int, runs: int) -> list[dict]:
    from api.db import get_engine
    from api.relevance import relevant_notams

    out = []
    with get_engine().connect() as conn:
        for src_iata, dst_iata in TEST_CORRIDORS:
            src, dst = IATA_TO_ICAO_CORRIDORS[src_iata], IATA_TO_ICAO_CORRIDORS[dst_iata]
            times, count = [], None
            for _ in range(runs + 1):  # first run warms caches, not counted
                result = relevant_notams(src, dst, etd, None, 0, fl_hi, corridor_nm, connection=conn)
                times.append(result["metadata"]["query_ms"])
                count = result["metadata"]["count"]
            out.append({"corridor": f"{src_iata}-{dst_iata}", "features": count,
                        "median_ms": round(statistics.median(times[1:]), 1),
                        "max_ms": round(max(times[1:]), 1)})
    return out


def to_markdown(r: dict) -> str:
    s = r["summary"]
    lines = ["# Retrieval evaluation (generated)", "",
             f"ETD {r['etd_utc']}, ETA = ETD + distance/450 kt, FL000-{r['fl_hi']:03d}, "
             f"corridor {r['corridor_nm']} NM.", "",
             f"AAI summary months available per NOF: {r['aai_summary_months_by_nof']}", "",
             "| Corridor | reference (autorouter, aerodrome) | in AAI data | TP | recall end-to-end "
             "| recall algorithmic | aerodrome-level retrieved | precision (aerodrome) | total retrieved |",
             "|---|---|---|---|---|---|---|---|---|"]
    for c in r["corridors"]:
        fmt = lambda v: "n/a" if v is None else f"{v:.1%}"  # noqa: E731
        lines.append(f"| {c['corridor']} | {c['reference']} | {c['in_aai_data']} | {c['true_positives']} | "
                     f"{fmt(c['recall_end_to_end'])} | {fmt(c['recall_algorithmic'])} | "
                     f"{c['retrieved_aerodrome_level']} | {fmt(c['precision_aerodrome_level'])} | "
                     f"{c['retrieved_total']} {c['retrieved_by_reason']} |")
    lines += ["", f"Summary: {json.dumps(s)}", ""]
    if r.get("db_timing"):
        lines += ["## PostGIS query time", "", "| Corridor | features | median ms | max ms |", "|---|---|---|---|"]
        lines += [f"| {t['corridor']} | {t['features']} | {t['median_ms']} | {t['max_ms']} |" for t in r["db_timing"]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--etd", default=DEFAULT_ETD)
    parser.add_argument("--corridor-nm", type=float, default=200.0)
    parser.add_argument("--fl-hi", type=int, default=350)
    parser.add_argument("--db", action="store_true", help="also time the PostGIS query")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)
    etd = datetime.fromisoformat(args.etd.replace("Z", "+00:00"))
    result = evaluate(etd, args.corridor_nm, args.fl_hi)
    if args.db:
        result["db_timing"] = time_db(etd, args.corridor_nm, args.fl_hi, args.runs)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "retrieval_eval.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (RESULTS / "retrieval_eval.md").write_text(to_markdown(result), encoding="utf-8")
    for c in result["corridors"]:
        print(f"{c['corridor']:8s} ref={c['reference']:3d} inAAI={c['in_aai_data']:3d} "
              f"TP={c['true_positives']:3d} recall={c['recall_end_to_end']} "
              f"alg={c['recall_algorithmic']} prec_ad={c['precision_aerodrome_level']} "
              f"retrieved={c['retrieved_total']}")
    print("summary:", result["summary"])
    if result.get("db_timing"):
        print("db timing:", result["db_timing"])


if __name__ == "__main__":
    main()
