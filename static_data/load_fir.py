"""Load FIR boundaries (VIDF, VABF, VECF, VOMF) from a GeoJSON file into ``fir``.

    python -m static_data.load_fir path/to/india_firs.geojson [--id-property ICAO]

The file must contain Polygon/MultiPolygon features with the FIR ICAO code in
a property (default tried: icao, ICAO, id, ident, designator).  Boundaries are
stored as MultiPolygon EPSG:4326; afterwards every airport inside a FIR gets
that fir_code.  Use an open dataset whose licence you have checked
(methodology §3: "Open GeoJSON (verify)").
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

KEYS = ("icao", "ICAO", "id", "ident", "designator", "ICAO_CODE")
INDIAN_FIRS = {"VIDF", "VABF", "VECF", "VOMF"}


def read_features(path: Path, id_property: str | None = None) -> list[tuple[str, dict]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for f in data.get("features", []):
        props = f.get("properties") or {}
        code = next((str(props[k]).upper() for k in ([id_property] if id_property else KEYS) if props.get(k)), None)
        geom = f.get("geometry") or {}
        if code in INDIAN_FIRS and geom.get("type") in ("Polygon", "MultiPolygon"):
            out.append((code, geom))
    return out


def main(argv=None):
    from sqlalchemy import text

    from api.db import get_engine

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path")
    ap.add_argument("--id-property")
    args = ap.parse_args(argv)
    feats = read_features(Path(args.path), args.id_property)
    with get_engine().begin() as conn:
        for code, geom in feats:
            conn.execute(text("""
                INSERT INTO fir (icao_code, boundary)
                VALUES (:c, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326)))
                ON CONFLICT (icao_code) DO UPDATE SET boundary = EXCLUDED.boundary"""),
                {"c": code, "g": json.dumps(geom)})
        n = conn.execute(text("""
            UPDATE airport a SET fir_code = f.icao_code FROM fir f
             WHERE f.boundary IS NOT NULL AND ST_Contains(f.boundary, a.location)""")).rowcount
    print(f"loaded {len(feats)} FIR boundaries; fir_code set on {n} airports")


if __name__ == "__main__":
    main()
