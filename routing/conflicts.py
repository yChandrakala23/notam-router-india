"""NOTAM conflict check for a candidate route (methodology layer 6).

A NOTAM being BLOCKING does **not** by itself block a route.  For every
relevant NOTAM (from ``api.relevance``) the route is tested on three axes:

* space    the sampled route (every 2 NM) enters the NOTAM area: circle
           (centre + radius, geodesic) or polygon (ray casting);
* vertical the aircraft's flight level *where it is inside the area* overlaps
           the NOTAM band.  The aircraft follows a simple profile: climb and
           descent at ``climb_fl_per_nm`` (default 3 FL/NM, i.e. ~300 ft/NM)
           capped at the cruise FL.  NULL NOTAM limits are unbounded;
* time     the time the aircraft is inside the area (ETD + along-track / TAS,
           widened by ``time_buffer_min``) overlaps the NOTAM validity.  D)
           schedules are not parsed, so the whole B)-C) window counts.

Outcomes (``conflict_type``):

HARD              BLOCKING and all three overlap -> route rejected
WARNING           RESTRICTIVE / ADVISORY and all three overlap
AIRPORT_BLOCKING  BLOCKING NOTAM for the source/destination aerodrome that is
                  valid at departure/arrival: no route can avoid it
AIRPORT_WARNING   non-blocking aerodrome NOTAM at source/destination
UNLOCALISED       NOTAM with no geometry (FIR-wide): cannot be placed on the
                  route; reported for manual review, never rejects
CLEARED           the route enters the area but is clear vertically or in time
                  (kept for explanation; not a conflict)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from routing.geo import gc_distance_nm, point_in_polygon, sample_path

# NOTAMs about an aerodrome's own facilities: they matter at the source and
# destination, not for aircraft overflying that aerodrome at cruise.
AERODROME_SCOPED = {"AERODROME", "RUNWAY"}
# With only the default aerodrome circle (AAI, no Q-line) these are local to that
# aerodrome (approach procedures, cranes near the field); navaid outages are
# kept as warnings because a VOR/DME can serve airways.
AERODROME_LOCAL_WHEN_DEFAULT = {"OBSTACLE", "PROCEDURE"}
# Activities whose area matters en route; without a Q-line their area is unknown.
ACTIVITY_CATEGORIES = {"NAV_WARNING", "AIRSPACE_RESTRICTION"}
DEFAULT_CLIMB_FL_PER_NM = 3.0
DEFAULT_TIME_BUFFER_MIN = 15.0


@dataclass
class Conflict:
    event_id: Optional[int]
    notam_id: Optional[str]
    conflict_type: str
    severity: Optional[str]
    category: Optional[str]
    explanation: str
    entry_nm: Optional[float] = None
    exit_nm: Optional[float] = None
    route_fl_range: Optional[tuple[int, int]] = None
    route_time_window: Optional[tuple[str, str]] = None

    def as_dict(self) -> dict:
        return asdict(self)


def _dt(value) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _hhmm(t: Optional[datetime]) -> str:
    return t.astimezone(timezone.utc).strftime("%d %H:%MZ") if t else "PERM"


def aircraft_fl(along_nm: float, total_nm: float, cruise_fl: int, climb: float) -> float:
    return min(float(cruise_fl), climb * along_nm, climb * max(0.0, total_nm - along_nm))


def _inside_intervals(samples, feature) -> list[tuple[float, float]]:
    props = feature["properties"]
    lat_c, lon_c, radius = props.get("center_lat"), props.get("center_lon"), props.get("radius_nm")
    geom = feature.get("geometry")
    if lat_c is not None and lon_c is not None and radius:
        flags = [gc_distance_nm(lat, lon, lat_c, lon_c) <= float(radius) for lat, lon, _ in samples]
    elif geom and geom.get("type") == "Polygon":
        ring = geom["coordinates"][0]
        flags = [point_in_polygon(lat, lon, ring) for lat, lon, _ in samples]
    else:
        return []
    intervals, start = [], None
    for (lat, lon, s), inside in zip(samples, flags):
        if inside and start is None:
            start = s
        if not inside and start is not None:
            intervals.append((start, prev_s))
            start = None
        prev_s = s
    if start is not None:
        intervals.append((start, samples[-1][2]))
    return intervals


def _describe(props) -> str:
    vd = props.get("valid_during") or {}
    lo = props.get("lower_fl")
    hi = props.get("upper_fl")
    band = f"FL{lo:03d}-{hi:03d}" if lo is not None and hi is not None else "FL band unknown (no Q-line)"
    where = ""
    if props.get("center_lat") is not None:
        lat, lon = props["center_lat"], props["center_lon"]
        where = f" near {abs(lat):.1f}{'N' if lat >= 0 else 'S'} {abs(lon):.1f}{'E' if lon >= 0 else 'W'}"
        if props.get("radius_nm"):
            where += f" (r {float(props['radius_nm']):.0f} NM)"
    code = props.get("q_code") or props.get("category")
    return (f"{props.get('notam_id')} {code}{where}, valid {vd.get('start')} to {vd.get('end') or 'PERM'}, {band}")


def check_route(points: list[tuple[float, float]], features: list[dict], *, src: str, dst: str,
                etd: datetime, tas_kt: float, cruise_fl: int,
                climb_fl_per_nm: float = DEFAULT_CLIMB_FL_PER_NM,
                time_buffer_min: float = DEFAULT_TIME_BUFFER_MIN, step_nm: float = 2.0) -> list[Conflict]:
    samples = sample_path(points, step_nm)
    total = samples[-1][2]
    eta = etd + timedelta(hours=total / tas_kt)
    buf = timedelta(minutes=time_buffer_min)
    out: list[Conflict] = []

    for f in features:
        p = f["properties"]
        sev = p.get("severity")
        start = _dt((p.get("valid_during") or {}).get("start"))
        end = _dt((p.get("valid_during") or {}).get("end"))
        lo = p.get("lower_fl") if p.get("lower_fl") is not None else 0
        hi = p.get("upper_fl") if p.get("upper_fl") is not None else 999
        desc = _describe(p)
        base = dict(event_id=p.get("event_id"), notam_id=p.get("notam_id"), severity=sev, category=p.get("category"))

        def active(t0: datetime, t1: datetime) -> bool:
            return (start is None or start <= t1 + buf) and (end is None or end >= t0 - buf)

        category = p.get("category")
        geom_source = p.get("geom_source") or "QLINE_CIRCLE"
        # An activity (launch, firing, restricted area) listed under an aerodrome
        # heading but without a Q-line has no known area: the default aerodrome
        # circle is not the activity area, so it is not placed on the route.
        if category in ACTIVITY_CATEGORIES and geom_source == "AERODROME_DEFAULT":
            if active(etd, eta):
                out.append(Conflict(**base, conflict_type="UNLOCALISED",
                                    explanation=f"{desc}: activity area not given (no Q-line; listed under "
                                                f"{p.get('icao_location')}); review manually"))
            continue

        # NOTAMs for the source/destination aerodrome.  Facility, procedure,
        # obstacle and navaid notices are judged at departure/arrival time.
        # Activities (restricted areas, firing, launches) with a real Q-line
        # area are checked spatially like any en-route area instead.
        if p.get("match_reason") == "AERODROME" and p.get("icao_location") in (src, dst) and \
                not (category in ACTIVITY_CATEGORIES and geom_source == "QLINE_CIRCLE"):
            if category in ACTIVITY_CATEGORIES:
                if active(etd, eta):
                    out.append(Conflict(**base, conflict_type="UNLOCALISED",
                                        explanation=f"{desc}: listed for {p['icao_location']} but its area is not "
                                                    "localised; review manually"))
                continue
            at = etd if p["icao_location"] == src else eta
            if not active(at, at):
                continue
            kind = "AIRPORT_BLOCKING" if sev == "BLOCKING" else "AIRPORT_WARNING"
            role = "departure" if p["icao_location"] == src else "arrival"
            out.append(Conflict(**base, conflict_type=kind,
                                explanation=f"{role} aerodrome {p['icao_location']}: {desc}; in force at "
                                            f"{_hhmm(at)}" + ("; no route choice avoids it" if kind == "AIRPORT_BLOCKING" else ""),
                                route_time_window=(_hhmm(at), _hhmm(at))))
            continue

        intervals = _inside_intervals(samples, f)
        if not intervals:
            if f.get("geometry") is None and p.get("center_lat") is None and category not in AERODROME_SCOPED:
                t0, t1 = etd, eta
                if active(t0, t1):
                    out.append(Conflict(**base, conflict_type="UNLOCALISED",
                                        explanation=f"{desc}: no geometry (FIR-wide); cannot be placed on the route, "
                                                    "review manually"))
            continue

        if p.get("icao_location") not in (src, dst) and (
                category in AERODROME_SCOPED or
                (category in AERODROME_LOCAL_WHEN_DEFAULT and geom_source == "AERODROME_DEFAULT")):
            out.append(Conflict(**base, conflict_type="CLEARED",
                                explanation=f"Overflies {p.get('icao_location')}: {desc} concerns that aerodrome's "
                                            "own facilities and does not restrict overflight"))
            continue

        for s0, s1 in intervals:
            fls = [aircraft_fl(s, total, cruise_fl, climb_fl_per_nm) for _, _, s in samples if s0 <= s <= s1]
            fl_min, fl_max = int(min(fls)), int(round(max(fls)))
            t0 = etd + timedelta(hours=s0 / tas_kt)
            t1 = etd + timedelta(hours=s1 / tas_kt)
            vertical = fl_min <= hi and fl_max >= lo
            temporal = active(t0, t1)
            where = f"route inside area from {s0:.0f} to {s1:.0f} NM at FL{fl_min:03d}-{fl_max:03d}, {_hhmm(t0)}-{_hhmm(t1)}"
            common = dict(entry_nm=round(s0, 1), exit_nm=round(s1, 1), route_fl_range=(fl_min, fl_max),
                          route_time_window=(_hhmm(t0), _hhmm(t1)))
            if vertical and temporal:
                kind = "HARD" if sev == "BLOCKING" else "WARNING"
                verb = "Crosses" if kind == "HARD" else "Passes through"
                out.append(Conflict(**base, conflict_type=kind, explanation=f"{verb} {desc}; {where}", **common))
            else:
                why = []
                if not vertical:
                    why.append(f"aircraft at FL{fl_min:03d}-{fl_max:03d} is outside FL{lo:03d}-{hi:03d}")
                if not temporal:
                    why.append("NOTAM not active while the aircraft is inside")
                out.append(Conflict(**base, conflict_type="CLEARED",
                                    explanation=f"Clear of {desc}: {'; '.join(why)} ({where})", **common))
    return out


def summarise(conflicts: list[Conflict]) -> dict:
    counts = {}
    for c in conflicts:
        counts[c.conflict_type] = counts.get(c.conflict_type, 0) + 1
    return counts
