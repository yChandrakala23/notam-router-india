"""Load Indian aerodromes from an OurAirports ``airports.csv`` into ``airport``.

    python -m static_data.load_airports path/to/airports.csv

Download airports.csv from https://ourairports.com/data/ (public domain).
Only rows with an Indian ICAO code (VA/VE/VI/VO + 2 letters) and type
large/medium/small_airport are loaded.  UPSERT: existing rows are updated,
fir_code is kept when the CSV has none (FIR assignment comes from
static_data/load_fir.py or migration 003).
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

INDIAN = re.compile(r"^V[AEIO][A-Z]{2}$")
TYPES = {"large_airport", "medium_airport", "small_airport"}


def read_ourairports(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            code = (r.get("gps_code") or r.get("ident") or "").strip().upper()
            if not INDIAN.match(code) or r.get("type") not in TYPES:
                continue
            try:
                lat, lon = float(r["latitude_deg"]), float(r["longitude_deg"])
            except (KeyError, ValueError):
                continue
            rows.append({"icao": code, "iata": (r.get("iata_code") or "").strip() or None,
                         "name": r.get("name"), "city": r.get("municipality") or None, "lat": lat, "lon": lon})
    return rows


def upsert(conn, rows: list[dict]) -> int:
    from sqlalchemy import text

    for r in rows:
        conn.execute(text("""
            INSERT INTO airport (icao_code, iata_code, name, city, location)
            VALUES (:icao, :iata, :name, :city, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
            ON CONFLICT (icao_code) DO UPDATE SET iata_code = COALESCE(EXCLUDED.iata_code, airport.iata_code),
                name = EXCLUDED.name, city = COALESCE(EXCLUDED.city, airport.city),
                location = EXCLUDED.location"""), r)
    return len(rows)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        raise SystemExit(__doc__)
    from api.db import get_engine

    rows = read_ourairports(Path(argv[0]))
    with get_engine().begin() as conn:
        print(f"upserted {upsert(conn, rows)} Indian aerodromes")
    print("Run static_data.load_fir afterwards to assign fir_code from FIR boundaries.")


if __name__ == "__main__":
    main()
