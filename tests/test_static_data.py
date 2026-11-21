"""Static-data loaders: file parsing only (no DB)."""

import json

from static_data.load_airports import read_ourairports
from static_data.load_fir import read_features


def test_read_ourairports(tmp_path):
    p = tmp_path / "airports.csv"
    p.write_text("id,ident,type,name,latitude_deg,longitude_deg,municipality,gps_code,iata_code\n"
                 "1,VIDP,large_airport,Indira Gandhi,28.56,77.10,Delhi,VIDP,DEL\n"
                 "2,OPKC,large_airport,Karachi,24.9,67.1,Karachi,OPKC,KHI\n"
                 "3,VA12,heliport,Helipad,19,72,Mumbai,,\n", encoding="utf-8")
    rows = read_ourairports(p)
    assert [r["icao"] for r in rows] == ["VIDP"] and rows[0]["iata"] == "DEL"


def test_read_fir_geojson(tmp_path):
    p = tmp_path / "fir.geojson"
    sq = {"type": "Polygon", "coordinates": [[[70, 20], [80, 20], [80, 30], [70, 30], [70, 20]]]}
    p.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"ICAO": "VIDF"}, "geometry": sq},
        {"type": "Feature", "properties": {"ICAO": "OPKR"}, "geometry": sq}]}), encoding="utf-8")
    assert [c for c, _ in read_features(p)] == ["VIDF"]
