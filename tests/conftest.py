import csv

import pytest

SHEET_FIELDS = ["nof", "notam_id", "location", "e_text", "pred_category", "pred_severity",
                "pred_method", "pred_conf", "human_category", "human_severity", "notes"]


def write_sheet(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=SHEET_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in SHEET_FIELDS})
    return path


@pytest.fixture
def sheet_writer(tmp_path):
    """Write a SYNTHETIC annotation sheet (test data only, not real labels)."""
    def _write(rows, name="sheet.csv"):
        return write_sheet(tmp_path / name, rows)
    return _write


def synthetic_human_rows(n_per_class=12):
    """SYNTHETIC labelled AAI-style rows across severities, with templates."""
    rows, k = [], 0
    words = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT"]   # -> 6 templates per class
    specs = [
        ("RUNWAY", "RESTRICTIVE", "SYNTHETIC {w} RWY {i:02d} CLSD DUE WIP SEGMENT {j}"),
        ("AERODROME", "ADVISORY", "SYNTHETIC {w} TWY {i:02d} CLSD FOR MAINT BAY {j}"),
        ("NAV_WARNING", "BLOCKING", "SYNTHETIC {w} LIVE FIRING RANGE {i:02d} ACT SFC TO FL{j}0"),
        ("NAVAID_COMMS", "RESTRICTIVE", "SYNTHETIC {w} VOR {i:02d} U/S DUE MAINT CH {j}"),
        ("OBSTACLE", "ADVISORY", "SYNTHETIC {w} CRANE {i:02d} ERECTED HGT {j}0 FT AGL"),
    ]
    for cat, sev, tmpl in specs:
        for i in range(n_per_class):
            k += 1
            rows.append({"nof": "VIDP", "notam_id": f"A{k:04d}/26", "location": "VIDP",
                         "e_text": tmpl.format(w=words[i % len(words)], i=i, j=i % 4), "pred_category": "AERODROME",
                         "pred_severity": "ADVISORY", "human_category": cat, "human_severity": sev,
                         "notes": f"synthetic case {k} reviewed"})
    return rows
