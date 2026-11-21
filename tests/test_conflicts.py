"""NOTAM-route conflict check: space + flight level + time (SYNTHETIC NOTAMs)."""

import pytest

from parsing.qline import circle_polygon
from routing.conflicts import aircraft_fl, check_route
from tests.routing_helpers import BOM, DEL, DIRECT, ETD, MID, feat


def kinds(features, fl=200, points=DIRECT):
    return [c.conflict_type for c in check_route(points, features, src="VIDP", dst="VABB", etd=ETD,
                                                  tas_kt=450, cruise_fl=fl)]


def test_blocking_inside_band_is_hard():
    out = check_route(DIRECT, [feat()], src="VIDP", dst="VABB", etd=ETD, tas_kt=450, cruise_fl=200)
    assert [c.conflict_type for c in out] == ["HARD"]
    c = out[0]
    assert 250 < c.entry_nm < 300 and c.route_fl_range == (200, 200) and "Crosses Z0001/26" in c.explanation


@pytest.mark.parametrize("change,expected", [
    (dict(), "HARD"),
    (dict(hi=150), "CLEARED"),                                        # aircraft above the band
    (dict(lo=250, hi=400), "CLEARED"),                                # aircraft below the band
    (dict(start="2026-11-05T08:00:00Z"), "CLEARED"),                  # starts after the crossing
    (dict(end="2026-11-05T05:00:00Z"), "CLEARED"),                    # ended before departure
    (dict(sev="RESTRICTIVE"), "WARNING"),
    (dict(sev="ADVISORY"), "WARNING"),
    (dict(lo=None, hi=None), "HARD"),                                 # unknown band -> conservative
    (dict(end=None), "HARD"),                                         # PERM
])
def test_axes(change, expected):
    assert kinds([feat(**change)]) == [expected]


def test_far_area_no_conflict():
    assert kinds([feat(lat=13.0, lon=80.0)]) == []


def test_time_buffer_widens_window():
    # NOTAM ends 10 min before the crossing (~06:35Z); default buffer is 15 min
    assert kinds([feat(end="2026-11-05T06:25:00Z")]) == ["HARD"]


def test_vertical_profile_climb():
    assert aircraft_fl(10, 600, 350, 3.0) == 30 and aircraft_fl(300, 600, 350, 3.0) == 350
    # low-level area 10 NM after departure: aircraft still climbing through it
    near = (DEL["lat"] - 0.14, DEL["lon"] - 0.07)
    assert kinds([feat(lat=near[0], lon=near[1], r=5, lo=0, hi=100)], fl=350) == ["HARD"]


def test_polygon_geometry_without_centre():
    poly = circle_polygon(MID[0], MID[1], 40)
    assert kinds([feat(lat=None, lon=None, r=None, geometry=poly)]) == ["HARD"]


def test_destination_closed_is_airport_blocking():
    f = feat(category="AERODROME", reason="AERODROME", loc="VABB", lat=BOM["lat"], lon=BOM["lon"], r=5,
             geom_source="AERODROME_DEFAULT", hi=None, lo=None)
    assert kinds([f]) == ["AIRPORT_BLOCKING"]
    # closure valid only after arrival -> not reported
    assert kinds([feat(category="AERODROME", reason="AERODROME", loc="VABB", start="2026-11-05T12:00:00Z")]) == []


def test_enroute_aerodrome_closure_does_not_block_overflight():
    f = feat(category="AERODROME", loc="VAAH", lat=MID[0], lon=MID[1], r=5, lo=None, hi=None,
             geom_source="AERODROME_DEFAULT")
    out = check_route(DIRECT, [f], src="VIDP", dst="VABB", etd=ETD, tas_kt=450, cruise_fl=350)
    assert [c.conflict_type for c in out] == ["CLEARED"] and "does not restrict overflight" in out[0].explanation


def test_activity_with_aerodrome_default_circle_is_unlocalised():
    f = feat(category="NAV_WARNING", loc="VOMM", geom_source="AERODROME_DEFAULT", lo=None, hi=None)
    assert kinds([f]) == ["UNLOCALISED"]
    f2 = feat(category="NAV_WARNING", loc="VABB", reason="AERODROME", geom_source="FIR_WIDE",
              lat=None, lon=None, r=None)
    assert kinds([f2]) == ["UNLOCALISED"]          # not an airport closure


def test_fir_wide_without_geometry():
    assert kinds([feat(lat=None, lon=None, r=None, geom_source="FIR_WIDE")]) == ["UNLOCALISED"]
    assert kinds([feat(lat=None, lon=None, r=None, geom_source="FIR_WIDE", category="AERODROME")]) == []


def test_aai_obstacle_at_enroute_aerodrome_is_local():
    f = feat(category="OBSTACLE", loc="VAAH", r=5, lo=None, hi=None, geom_source="AERODROME_DEFAULT", sev="ADVISORY")
    assert kinds([f], fl=350) == ["CLEARED"]
    # the same obstacle from a Q-line (real FL band) is judged on its band
    q = feat(category="OBSTACLE", r=5, lo=0, hi=4, sev="ADVISORY")
    assert kinds([q], fl=350) == ["CLEARED"]
    # navaid outages at an en-route aerodrome stay warnings
    n = feat(category="NAVAID_COMMS", loc="VAAH", r=5, lo=None, hi=None, geom_source="AERODROME_DEFAULT",
             sev="RESTRICTIVE")
    assert kinds([n], fl=350) == ["WARNING"]
