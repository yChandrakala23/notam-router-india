
import json
from pathlib import Path
from collections import Counter

DATA_DIR = Path("data/autorouter")

records = []
for path in sorted(DATA_DIR.glob("*_notams.jsonl")):
    with path.open(encoding="utf-8") as f:
        records.extend(json.loads(line) for line in f if line.strip())

print("=== AUTOROUTER REFERENCE VALIDATION ===")
print("Records:", len(records))

# 1. Inspect Q-code component combinations.
print("\n--- Q-code components ---")
pairs = Counter(
    (
        (r.get("code23") or "").strip(),
        (r.get("code45") or "").strip(),
    )
    for r in records
)
for (code23, code45), count in pairs.most_common():
    print(f"{code23}/{code45}: {count}")

# 2. Inspect coordinate ranges.
# Do not assume the encoding until we verify it.
print("\n--- Coordinate raw-value ranges ---")
for field in ("lat", "lon", "nelat", "nelon", "swlat", "swlon"):
    values = [
        r[field] for r in records
        if isinstance(r.get(field), (int, float))
    ]
    if values:
        print(
            f"{field}: min={min(values)}, "
            f"max={max(values)}, count={len(values)}"
        )

# 3. Check replacement references.
print("\n--- Replacement records ---")
replacements = [r for r in records if r.get("type") == "R"]
print("Replacement records:", len(replacements))

for r in replacements[:10]:
    print({
        "id": r.get("id"),
        "nof": r.get("nof"),
        "series": r.get("series"),
        "number": r.get("number"),
        "year": r.get("year"),
        "referredseries": r.get("referredseries"),
        "referrednumber": r.get("referrednumber"),
        "referredyear": r.get("referredyear"),
    })

# 4. Inspect geometry field completeness.
print("\n--- Geometry completeness ---")
for field in ("lat", "lon", "radius", "nelat", "nelon", "swlat", "swlon"):
    count = sum(r.get(field) is not None for r in records)
    print(f"{field}: {count}/{len(records)} present")

# 5. Check identifiers and record types.
print("\n--- Record types ---")
print(Counter(r.get("type") for r in records))
print("Missing IDs:", sum(r.get("id") is None for r in records))
print("Missing Item E:", sum(not r.get("iteme") for r in records))

print("\nValidation inspection complete. No source data modified.")
