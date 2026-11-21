"""SYNTHETIC NOTAM features for routing tests (not real NOTAMs)."""

from datetime import datetime, timezone

from db.reference_airports import reference_airports
from routing.geo import intermediate

ETD = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)
AP = reference_airports()
DEL, BOM = AP["VIDP"], AP["VABB"]
MID = intermediate(DEL["lat"], DEL["lon"], BOM["lat"], BOM["lon"], 0.5)
DIRECT = [(DEL["lat"], DEL["lon"]), (BOM["lat"], BOM["lon"])]


def feat(eid=1, sev="BLOCKING", lo=0, hi=250, lat=MID[0], lon=MID[1], r=40, start="2026-11-05T00:00:00Z",
         end="2026-11-06T00:00:00Z", reason="CORRIDOR", loc=None, category="AIRSPACE_RESTRICTION",
         geom_source="QLINE_CIRCLE", geometry=None):
    return {"type": "Feature", "id": eid, "geometry": geometry, "properties": {
        "event_id": eid, "notam_id": f"Z{eid:04d}/26", "severity": sev, "category": category, "q_code": "QRTCA",
        "lower_fl": lo, "upper_fl": hi, "valid_during": {"start": start, "end": end}, "radius_nm": r,
        "center_lat": lat, "center_lon": lon, "match_reason": reason, "icao_location": loc,
        "geom_source": geom_source}}
