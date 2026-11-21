
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from pathlib import Path
from collections import Counter
from datetime import datetime

from ingestion.autorouter_adapter import normalize_notam

DATA_DIR = Path("data/autorouter")

records = []
for path in sorted(DATA_DIR.glob("*_notams.jsonl")):
    with path.open(encoding="utf-8") as f:
        records.extend(
            json.loads(line)
            for line in f
            if line.strip()
        )

print("=== BATCH ADAPTER VALIDATION ===")
print("Input records:", len(records))

normalized = []
errors = []

for record in records:
    try:
        normalized.append(normalize_notam(record))
    except Exception as exc:
        errors.append({
            "source_id": record.get("id"),
            "error": str(exc),
        })

print("Successfully normalized:", len(normalized))
print("Conversion errors:", len(errors))

if errors:
    print("\nFirst errors:")
    for error in errors[:10]:
        print(error)

# Check essential fields.
print("\n--- Essential field completeness ---")
for field in (
    "source_id",
    "fir",
    "start_validity_utc",
    "latitude",
    "longitude",
    "item_e",
):
    present = sum(
        row.get(field) is not None
        for row in normalized
    )
    print(f"{field}: {present}/{len(normalized)}")

# Check decoded coordinate ranges.
invalid_coordinates = [
    row for row in normalized
    if row["latitude"] is None
    or row["longitude"] is None
    or not -90 <= row["latitude"] <= 90
    or not -180 <= row["longitude"] <= 180
]
print("\nInvalid decoded coordinates:", len(invalid_coordinates))

# Check validity interval ordering.
# Open-ended end times are represented by None.
invalid_intervals = []

for row in normalized:
    start = row["start_validity_utc"]
    end = row["end_validity_utc"]

    if start and end and end < start:
        invalid_intervals.append(row["source_id"])

print("Reversed validity intervals:", len(invalid_intervals))

# Summarize records without deciding whether they are active.
print("\n--- Record classification ---")
print("Types:", Counter(row["notam_type"] for row in normalized))
print(
    "Open-ended validity:",
    sum(row["end_validity_open_ended"] for row in normalized),
)
print(
    "Estimated validity:",
    sum(row["validity_estimation"] == "EST" for row in normalized),
)
print(
    "Suppressed:",
    sum(row["suppressed"] is True for row in normalized),
)

print("\nBatch validation complete. No source data modified.")
