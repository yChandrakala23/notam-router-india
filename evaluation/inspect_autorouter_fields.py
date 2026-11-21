
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

DATA_DIR = Path("data/autorouter")

# Autorouter Garmin coordinate encoding:
# Decimal degrees = raw value * 90 / 2^30
GARMIN_SCALE = 90 / (1 << 30)

records = []

for path in sorted(DATA_DIR.glob("*_notams.jsonl")):
    with path.open(encoding="utf-8") as f:
        records.extend(
            json.loads(line)
            for line in f
            if line.strip()
        )

print("=== AUTOROUTER FIELD ENCODING INSPECTION ===")
print("Total records:", len(records))

# 1. Decode coordinates using the Garmin formula.
print("\n--- Decoded coordinates ---")

for r in records[:10]:
    lat_raw = r.get("lat")
    lon_raw = r.get("lon")

    latitude = (
        round(lat_raw * GARMIN_SCALE, 6)
        if isinstance(lat_raw, (int, float))
        else None
    )
    longitude = (
        round(lon_raw * GARMIN_SCALE, 6)
        if isinstance(lon_raw, (int, float))
        else None
    )

    print({
        "notam_id": r.get("id"),
        "airport_query_result": r.get("itema"),
        "lat_raw": lat_raw,
        "lon_raw": lon_raw,
        "latitude_deg": latitude,
        "longitude_deg": longitude,
        "radius_raw": r.get("radius"),
    })

# 2. Inspect Q-code components and related fields.
print("\n--- Q-line reconstruction candidates ---")

for r in records[:10]:
    code23 = (r.get("code23") or "").strip()
    code45 = (r.get("code45") or "").strip()

    print({
        "notam_id": r.get("id"),
        "fir": r.get("fir"),
        "code23": code23,
        "code45": code45,
        "candidate_q_code": "Q" + code23 + code45,
        "traffic": (r.get("traffic") or "").strip(),
        "purpose": (r.get("purpose") or "").strip(),
        "scope": (r.get("scope") or "").strip(),
        "lower": r.get("lower"),
        "upper": r.get("upper"),
    })

# 3. Inspect validity fields and identify the open-ended sentinel.
print("\n--- Validity fields ---")

OPEN_ENDED_SENTINEL = 2147483647

for field in ("startvalidity", "endvalidity", "estimation"):
    values = [
        r.get(field)
        for r in records
        if r.get(field) is not None
    ]

    print(f"\n{field}:")
    print("Python types:", sorted({type(v).__name__ for v in values}))
    print("Sample values:", values[:5])

    if field in ("startvalidity", "endvalidity"):
        sentinel_count = sum(
            value == OPEN_ENDED_SENTINEL
            for value in values
        )
        print("Open-ended sentinel occurrences:", sentinel_count)

        timestamps = [
            value for value in values
            if isinstance(value, (int, float))
            and value != OPEN_ENDED_SENTINEL
        ]

        for value in timestamps[:5]:
            print(
                "UTC:",
                datetime.fromtimestamp(
                    value, tz=timezone.utc
                ).isoformat()
            )

# 4. Inspect replacement references and record types.
print("\n--- Record types ---")
print(Counter(r.get("type") for r in records))

replacements = [
    r for r in records
    if r.get("type") == "R"
]

print("Replacement records:", len(replacements))

for r in replacements[:5]:
    print({
        "id": r.get("id"),
        "series": r.get("series"),
        "number": r.get("number"),
        "year": r.get("year"),
        "referredseries": r.get("referredseries"),
        "referrednumber": r.get("referrednumber"),
        "referredyear": r.get("referredyear"),
    })

# 5. Inspect bounding-box coordinates using the same formula.
print("\n--- Bounding-box coordinates ---")

for r in records[:5]:
    decoded = {}

    for field in ("nelat", "nelon", "swlat", "swlon"):
        raw = r.get(field)
        decoded[field] = (
            round(raw * GARMIN_SCALE, 6)
            if isinstance(raw, (int, float))
            else None
        )

    print({
        "notam_id": r.get("id"),
        **decoded,
    })

# 6. Check important field completeness.
print("\n--- Field completeness ---")

for field in (
    "id", "fir", "code23", "code45",
    "startvalidity", "endvalidity",
    "lat", "lon", "radius", "iteme",
):
    present = sum(
        r.get(field) is not None
        for r in records
    )
    print(f"{field}: {present}/{len(records)} present")

print("\nInspection complete. Source files were not modified.")
