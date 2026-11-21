
"""Aggregate audit of NOTAM lifecycle resolution.

Reads local Autorouter records without modifying them.
Does not print raw NOTAM text or individual identifiers.
"""

import sys
import json
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.notam_lifecycle import resolve_notam_lifecycle

DATA_DIR = PROJECT_ROOT / "data" / "autorouter"

records = []

for path in sorted(DATA_DIR.glob("*_notams.jsonl")):
    with path.open(encoding="utf-8") as f:
        records.extend(
            json.loads(line)
            for line in f
            if line.strip()
        )

print("=== NOTAM LIFECYCLE SNAPSHOT AUDIT ===")
print("Input records:", len(records))

as_of = datetime.now(timezone.utc)
results = resolve_notam_lifecycle(records, as_of=as_of)

print("Results produced:", len(results))
print("Audit time (UTC):", as_of.isoformat())

print("\n--- Lifecycle statuses ---")
for status, count in Counter(
    row["lifecycle_status"] for row in results
).most_common():
    print(f"{status}: {count}")

print("\n--- Reference resolution ---")
for status, count in Counter(
    row["reference_resolution"] for row in results
).most_common():
    print(f"{status}: {count}")

print("\n--- Validity statuses ---")
for status, count in Counter(
    row["validity_status"] for row in results
).most_common():
    print(f"{status}: {count}")

print("\n--- Results by record type ---")
for record_type in sorted({
    row["record_type"] for row in results
}):
    subset = [
        row for row in results
        if row["record_type"] == record_type
    ]

    print(f"\nType {record_type}: {len(subset)}")
    for status, count in Counter(
        row["lifecycle_status"] for row in subset
    ).most_common():
        print(f"  {status}: {count}")

print("\n--- Consistency checks ---")
print(
    "Duplicate source IDs:",
    len(records) - len({
        record.get("id")
        for record in records
        if record.get("id") is not None
    }),
)
print(
    "Records without a source ID:",
    sum(record.get("id") is None for record in records),
)
print(
    "Records with unresolved references:",
    sum(
        row["lifecycle_status"] == "unresolved_reference"
        for row in results
    ),
)
print(
    "Records superseded by known references:",
    sum(bool(row["superseded_by"]) for row in results),
)
print(
    "Records linked to known cancellations:",
    sum(bool(row["cancelled_by"]) for row in results),
)

print("\nAudit complete. Source files were not modified.")
