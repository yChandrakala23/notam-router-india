"""Airport reference points shared by SQL seed and Python reference code.

Single source of truth: the VALUES list in
``db/migrations/003_reference_rows_minimal.sql``.  This module parses it so the
offline (no-database) retrieval reference and the evaluation scripts use the
same coordinates as PostGIS.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

SEED_SQL = Path(__file__).resolve().parent / "migrations" / "003_reference_rows_minimal.sql"

_ROW = re.compile(
    r"\(\s*'(?P<icao>[A-Z]{4})'\s*,\s*(?:'(?P<iata>[A-Z]{3})'|NULL)\s*,\s*'(?P<name>(?:[^']|'')*)'\s*,"
    r"\s*'(?P<city>(?:[^']|'')*)'\s*,\s*'(?P<fir>[A-Z]{4})'\s*,\s*(?P<lat>-?\d+(?:\.\d+)?)\s*,"
    r"\s*(?P<lon>-?\d+(?:\.\d+)?)\s*\)"
)

IATA_TO_ICAO_CORRIDORS = {
    "DEL": "VIDP", "BOM": "VABB", "BLR": "VOBL", "MAA": "VOMM", "CCU": "VECC", "SXR": "VISR",
}
TEST_CORRIDORS = [("DEL", "BOM"), ("DEL", "BLR"), ("BOM", "MAA"), ("CCU", "DEL"), ("DEL", "SXR")]


@lru_cache(maxsize=1)
def reference_airports() -> dict[str, dict]:
    text = SEED_SQL.read_text(encoding="utf-8")
    airports = {}
    for m in _ROW.finditer(text):
        airports[m.group("icao")] = {
            "icao": m.group("icao"), "iata": m.group("iata"), "name": m.group("name"),
            "fir": m.group("fir"), "lat": float(m.group("lat")), "lon": float(m.group("lon")),
        }
    return airports
