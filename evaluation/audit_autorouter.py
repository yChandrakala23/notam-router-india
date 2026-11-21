
import json
from collections import Counter
from pathlib import Path

DATA_DIR = Path("data/autorouter")
files = sorted(DATA_DIR.glob("*_notams.jsonl"))

records = []
for path in files:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                row["_source_file"] = path.name
                records.append(row)

print("\n=== AUTOROUTER DATA AUDIT ===")
print("Files:", len(files))
print("Total records:", len(records))
print("Unique IDs:", len({r.get("id") for r in records if r.get("id") is not None}))
print("Duplicate IDs across files:", len(records) - len({
    r.get("id") for r in records if r.get("id") is not None
}))

print("\n=== RECORDS PER FILE ===")
for path in files:
    count = sum(r["_source_file"] == path.name for r in records)
    print(f"{path.name}: {count}")

print("\n=== Q-CODE COMPONENTS ===")
print("code23:", Counter((r.get("code23") or "").strip() for r in records).most_common(15))
print("code45:", Counter((r.get("code45") or "").strip() for r in records).most_common(15))

print("\n=== DATA COMPLETENESS ===")
for field in [
    "fir", "code23", "code45", "traffic", "purpose", "scope",
    "lower", "upper", "lat", "lon", "radius",
    "startvalidity", "endvalidity", "iteme"
]:
    present = sum(r.get(field) is not None and r.get(field) != "" for r in records)
    print(f"{field:16} {present:3}/{len(records)} present")

print("\n=== STATUS ===")
print("Suppressed:", sum(bool(r.get("suppressed")) for r in records))
print("NOTAM types:", Counter(str(r.get("type")) for r in records))
print("FIRs:", Counter(str(r.get("fir")) for r in records))
print("Airports:", Counter(
    airport
    for r in records
    for airport in (r.get("itema") or [])
))

print("\n=== VALIDITY CHECK ===")
print("Records with missing start:", sum(not r.get("startvalidity") for r in records))
print("Records with missing end:", sum(not r.get("endvalidity") for r in records))
print("Records with reversed validity:", sum(
    r.get("startvalidity") is not None
    and r.get("endvalidity") is not None
    and r["endvalidity"] < r["startvalidity"]
    for r in records
))

print("\nAudit complete. Raw records were not modified.")
