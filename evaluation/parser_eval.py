"""Parser evaluation on real NOTAMs (Person A).

    python -m evaluation.parser_eval

Writes evaluation/results/parser_eval.json and parser_eval.md.

Three test sets, each with an explicit reference:

A. AAI monthly summaries (public, ~1.3k unique records, no Q-line).
   * parse success / failure reasons for every unique record;
   * **independent field accuracy**: AAI records whose identity (NOF + id)
     also appears in the autorouter snapshot are compared field-by-field
     with autorouter's structured values (B start, C end / PERM, EST,
     aerodrome).  autorouter is an independent provider, so this is a real
     accuracy measurement, but only on the overlapping subset.

B. autorouter snapshot (commercial, Q-line fields as JSON).
   The record is rendered to ICAO text and parsed back; parsed fields are
   compared with the source JSON.  This measures the Q-line / A-B-C parser on
   real values and real field-width variety, *not* on independently typed
   text (documented limitation).  Geometry validity is checked for every
   circle.

C. Real ICAO-text NOTAM fixtures (ISRO launch NOTAMs) with hand-checked
   expected values.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from api.relevance import gc_distance_nm
from parsing.aai_summary import content_hash, parse_summary_records
from parsing.autorouter_record import GARMIN_SCALE, OPEN_ENDED_SENTINEL, parse_autorouter_record
from parsing.qline import circle_polygon, parse_notam

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evaluation" / "results"


def _jsonl(pattern: str, directory: Path) -> list[dict]:
    rows = []
    for path in sorted(directory.glob(pattern)):
        with path.open(encoding="utf-8") as handle:
            rows += [json.loads(line) for line in handle if line.strip()]
    return rows


def _ts(value):
    if value is None or value == OPEN_ENDED_SENTINEL:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).replace(second=0, microsecond=0)


def _acc(counter: Counter) -> dict:
    out = {}
    for field in sorted({k for k, _ in counter}):
        ok, total = counter[(field, True)], counter[(field, True)] + counter[(field, False)]
        out[field] = {"correct": ok, "total": total,
                      "accuracy": round(ok / total, 4) if total else None}
    return out


def evaluate_aai(aai_dir: Path, autorouter: list[dict]) -> dict:
    blocks = _jsonl("aai_*.jsonl", aai_dir)
    parsed = parse_summary_records(blocks)
    unique = {}
    for block, item in zip(blocks, parsed):
        unique.setdefault(content_hash(item.nof, block["raw_text"]), item)
    items = list(unique.values())
    ok = [i for i in items if i.ok]
    failures = Counter(e for i in items for e in i.errors)

    by_identity = {(r.get("nof"), f"{r['series']}{int(r['number']):04d}/{int(r['year']) % 100:02d}"): r
                   for r in autorouter}
    fields = Counter()
    mismatches = []
    matched = 0
    latest = {}
    for item in ok:
        latest[(item.nof, item.notam_id)] = item
    for key, item in latest.items():
        ref = by_identity.get(key)
        if ref is None:
            continue
        matched += 1
        checks = {
            "notam_id": True,  # matched on it
            "valid_from_B": item.valid_from == _ts(ref.get("startvalidity")),
            "valid_until_C": item.valid_until == _ts(ref.get("endvalidity")),
            "permanent": item.is_permanent == (ref.get("endvalidity") == OPEN_ENDED_SENTINEL),
            "estimated_end": item.end_estimated == ((ref.get("estimation") or "").upper() == "EST"),
        }
        items_a = ref.get("itema") or []
        if item.location is not None:
            checks["location_A"] = item.location in items_a
        for field, good in checks.items():
            fields[(field, good)] += 1
            if not good:
                mismatches.append({"notam": "/".join(key), "field": field})
    location_known = sum(1 for i in ok if i.location)
    return {
        "observations": len(blocks),
        "unique_records": len(items),
        "unique_identities": len(latest),
        "parsed_ok": len(ok),
        "parse_success_rate": round(len(ok) / len(items), 4) if items else None,
        "failures": dict(failures),
        "location_assigned": location_known,
        "location_assigned_rate": round(location_known / len(ok), 4) if ok else None,
        "independent_check": {
            "reference": "autorouter structured fields (same NOTAM identity)",
            "matched_identities": matched,
            "field_accuracy": _acc(fields),
            "mismatches": mismatches[:50],
        },
    }


def evaluate_autorouter(records: list[dict]) -> dict:
    fields = Counter()
    geometry = Counter()
    mismatches = []
    for record in records:
        p = parse_autorouter_record(record)
        q = p.qline
        lat = record["lat"] * GARMIN_SCALE if isinstance(record.get("lat"), int) else None
        lon = record["lon"] * GARMIN_SCALE if isinstance(record.get("lon"), int) else None
        expected = {
            "parsed": True,
            "notam_id": f"{record['series']}{int(record['number']):04d}/{int(record['year']) % 100:02d}",
            "action": (record.get("type") or "").strip(),
            "fir": record.get("fir"),
            "q_code": f"Q{record.get('code23', '').strip()}{record.get('code45', '').strip()}",
            "traffic": (record.get("traffic") or "").strip(),
            "purpose": (record.get("purpose") or "").strip(),
            "scope": (record.get("scope") or "").strip(),
            "lower_fl": record.get("lower"),
            "upper_fl": record.get("upper"),
            "radius_nm": float(record["radius"]) if record.get("radius") is not None else None,
            "location_A": list(record.get("itema") or []),
            "valid_from_B": _ts(record.get("startvalidity")),
            "valid_until_C": _ts(record.get("endvalidity")),
        }
        got = {
            "parsed": p.ok and q is not None,
            "notam_id": p.notam_id, "action": p.action,
            "fir": q and q.fir, "q_code": q and q.q_code, "traffic": q and q.traffic,
            "purpose": q and q.purpose, "scope": q and q.scope,
            "lower_fl": q and q.lower_fl, "upper_fl": q and q.upper_fl,
            "radius_nm": q and q.radius_nm, "location_A": p.locations,
            "valid_from_B": p.valid_from, "valid_until_C": p.valid_until,
        }
        for field, value in expected.items():
            good = got[field] == value
            fields[(field, good)] += 1
            if not good:
                mismatches.append({"id": expected["notam_id"], "field": field,
                                   "expected": str(value), "got": str(got[field])})
        # centre: Q-line resolution is 1 arc-minute -> max error 0.5'
        if q and q.has_circle and lat is not None:
            centre_ok = abs(q.latitude - lat) <= 0.5 / 60 + 1e-9 and abs(q.longitude - lon) <= 0.5 / 60 + 1e-9
            fields[("centre_within_0.5_arcmin", centre_ok)] += 1
            poly = circle_polygon(q.latitude, q.longitude, max(q.radius_nm, 1.0))
            ring = poly["coordinates"][0]
            closed = ring[0] == ring[-1] and len(ring) >= 4
            radii = [gc_distance_nm(q.latitude, q.longitude, y, x) for x, y in ring[:-1]]
            radius_ok = all(abs(r - max(q.radius_nm, 1.0)) / max(q.radius_nm, 1.0) < 0.001 for r in radii)
            geometry[("valid_polygon", closed and radius_ok)] += 1
    return {
        "records": len(records),
        "note": "rendered from structured JSON then parsed (round trip), see module docstring",
        "field_accuracy": _acc(fields),
        "geometry": _acc(geometry),
        "mismatches": mismatches[:50],
    }


FIXTURE_EXPECTED = {
    "pslv_c47.txt": dict(notam_id="A2390/19", action="N", q_code="QWMLW", fir="VOMF", lower_fl=0,
                         upper_fl=999, locations=["VOMF"], valid_from="2019-11-10T03:30:00+00:00",
                         valid_until="2019-12-09T05:30:00+00:00", schedule="0330-0530"),
    "pslv_c48.txt": dict(notam_id="A2802/19", action="N", q_code="QWMLW", fir="VOMF", lower_fl=0,
                         upper_fl=999, locations=["VOMF"], valid_from="2019-12-11T09:30:00+00:00",
                         valid_until="2019-12-13T10:30:00+00:00",
                         schedule="11 0930-1130, 12 0900-1100 AND 13 0830-1030"),
    "gslv_m1.txt": dict(notam_id="A1550/19", action="N", q_code="QWMLW", fir="VOMF", lower_fl=0,
                        upper_fl=999, locations=["VOMF"], valid_from="2019-07-17T21:00:00+00:00",
                        valid_until="2019-07-31T10:00:00+00:00",
                        schedule="BTN 2100-2200 ON 17 JUL AND BTN 0830-1000 ON 18-31 JUL"),
}


def evaluate_fixtures(directory: Path) -> dict:
    fields = Counter()
    for name, expected in FIXTURE_EXPECTED.items():
        p = parse_notam((directory / name).read_text(encoding="utf-8"))
        got = dict(notam_id=p.notam_id, action=p.action, q_code=p.qline and p.qline.q_code,
                   fir=p.qline and p.qline.fir, lower_fl=p.qline and p.qline.lower_fl,
                   upper_fl=p.qline and p.qline.upper_fl, locations=p.locations,
                   valid_from=p.valid_from and p.valid_from.isoformat(),
                   valid_until=p.valid_until and p.valid_until.isoformat(), schedule=p.schedule)
        for field, value in expected.items():
            fields[(field, got[field] == value)] += 1
    return {"records": len(FIXTURE_EXPECTED), "field_accuracy": _acc(fields)}


def _overall(acc: dict) -> dict:
    ok = sum(v["correct"] for v in acc.values())
    total = sum(v["total"] for v in acc.values())
    return {"correct": ok, "total": total, "accuracy": round(ok / total, 4) if total else None}


def to_markdown(r: dict) -> str:
    a, b, c = r["aai"], r["autorouter"], r["fixtures"]
    lines = ["# Parser evaluation (generated)", "", f"Generated: {r['generated_at']}", "",
             "## A. AAI monthly summaries (public, no Q-line)", "",
             f"- observations (PDF blocks): {a['observations']}",
             f"- unique raw records (content hash): {a['unique_records']}",
             f"- unique NOTAM identities: {a['unique_identities']}",
             f"- parsed without error: {a['parsed_ok']} ({a['parse_success_rate']:.2%})",
             f"- failures: {a['failures']}",
             f"- aerodrome/FIR location assigned from section heading: "
             f"{a['location_assigned']} ({a['location_assigned_rate']:.2%})", "",
             f"Independent check vs autorouter on {a['independent_check']['matched_identities']} "
             "overlapping NOTAMs:", "", "| field | correct / total | accuracy |", "|---|---|---|"]
    for field, v in a["independent_check"]["field_accuracy"].items():
        lines.append(f"| {field} | {v['correct']} / {v['total']} | {v['accuracy']:.2%} |")
    lines += ["", f"Overall: {r['summary']['aai_independent']}", "",
              "## B. autorouter records (Q-line round trip)", "",
              f"Records: {b['records']}. {b['note']}.", "",
              "| field | correct / total | accuracy |", "|---|---|---|"]
    for field, v in b["field_accuracy"].items():
        lines.append(f"| {field} | {v['correct']} / {v['total']} | {v['accuracy']:.2%} |")
    lines += ["", f"Overall: {r['summary']['autorouter_round_trip']}", "",
              f"Geometry: {b['geometry']}", "",
              "## C. Real ICAO-text fixtures (hand-checked)", "",
              f"Overall: {r['summary']['fixtures']}", "",
              "## Totals", "", f"Real NOTAM records exercised: {r['summary']['real_records_tested']}"]
    return "\n".join(lines)


def main():
    autorouter = _jsonl("*_notams.jsonl", ROOT / "data" / "autorouter")
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "aai": evaluate_aai(ROOT / "data" / "raw", autorouter),
        "autorouter": evaluate_autorouter(autorouter),
        "fixtures": evaluate_fixtures(ROOT / "tests" / "fixtures" / "qline"),
    }
    result["summary"] = {
        "aai_independent": _overall(result["aai"]["independent_check"]["field_accuracy"]),
        "autorouter_round_trip": _overall(result["autorouter"]["field_accuracy"]),
        "fixtures": _overall(result["fixtures"]["field_accuracy"]),
        "real_records_tested": result["aai"]["unique_records"] + result["autorouter"]["records"]
        + result["fixtures"]["records"],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "parser_eval.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (RESULTS / "parser_eval.md").write_text(to_markdown(result), encoding="utf-8")
    print(json.dumps(result["summary"], indent=1))
    print("AAI parse success:", result["aai"]["parse_success_rate"], "failures:", result["aai"]["failures"])
    print("Geometry:", result["autorouter"]["geometry"])


if __name__ == "__main__":
    main()
