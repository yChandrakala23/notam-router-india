
import json
import sys
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data" / "autorouter"

records = []
for path in sorted(DATA_DIR.glob("*_notams.jsonl")):
    with path.open(encoding="utf-8") as f:
        records.extend(
            json.loads(line)
            for line in f
            if line.strip()
        )


def norm(value):
    return str(value).strip().upper() if value is not None else None


# Index records by series, number, and year, regardless of office.
by_number = {}
for record in records:
    key = (
        norm(record.get("series")),
        norm(record.get("number")),
        norm(record.get("year")),
    )
    by_number.setdefault(key, []).append(record)

replacements = [
    record for record in records
    if norm(record.get("type")) == "R"
]

diagnoses = Counter()

for record in replacements:
    ref_series = norm(record.get("referredseries"))
    ref_number = norm(record.get("referrednumber"))
    ref_year = norm(record.get("referredyear"))

    if not all((ref_series, ref_number, ref_year)):
        diagnoses["missing_reference_fields"] += 1
        continue

    key = (ref_series, ref_number, ref_year)
    candidates = by_number.get(key, [])

    # A replacement must not resolve to itself.
    candidates = [
        candidate for candidate in candidates
        if candidate.get("id") != record.get("id")
    ]

    if len(candidates) == 1:
        diagnoses["unique_series_number_year_match"] += 1
    elif len(candidates) > 1:
        diagnoses["ambiguous_series_number_year_match"] += 1
    else:
        diagnoses["target_absent_from_snapshot"] += 1

print("=== REPLACEMENT REFERENCE DIAGNOSTIC ===")
print("Records in snapshot:", len(records))
print("Replacement records:", len(replacements))

for status, count in diagnoses.most_common():
    print(f"{status}: {count}")

print("\nNo raw NOTAM text or identifiers printed.")
print("Source files were not modified.")
