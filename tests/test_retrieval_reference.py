"""Relevant-NOTAM retrieval semantics, on SYNTHETIC events (no database).

The same rules are implemented in SQL (api.relevance.RELEVANT_SQL);
tests/test_db_integration.py checks that both agree on a live PostGIS.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from api.relevance import (RetrievalError, UnknownAirport, estimate_eta, point_to_arc_nm,
                           relevant_notams_from_file, relevant_notams_reference)

FIXTURE = Path("tests/fixtures/synthetic_notam_events.json")
EVENTS = json.loads(FIXTURE.read_text(encoding="utf-8"))["events"]
ETD = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)
ETA = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)


def cases(result):
    by_id = {e["event_id"]: e["synthetic_case"] for e in EVENTS}
    return {by_id[f["properties"]["event_id"]]: f for f in result["features"]}


def run(**kw):
    args = dict(src="VIDP", dst="VABB", etd_utc=ETD, eta_utc=ETA, fl_lo=0, fl_hi=350, corridor_nm=200)
    args.update(kw)
    return relevant_notams_reference(EVENTS, **args)


def test_expected_relevant_set():
    got = cases(run())
    assert set(got) == {"corridor_blocking", "destination_closed_low_fl", "permanent",
                        "fir_wide_src", "corridor_edge_175nm"}
    assert got["destination_closed_low_fl"]["properties"]["match_reason"] == "AERODROME"
    assert got["corridor_blocking"]["properties"]["match_reason"] == "CORRIDOR"
    assert got["fir_wide_src"]["geometry"] is None


def test_narrow_corridor_drops_edge_case():
    assert "corridor_edge_175nm" not in cases(run(corridor_nm=150))


def test_fl_window_matters_except_at_aerodromes():
    got = cases(run(fl_lo=410, fl_hi=430))
    assert "fl_above_cruise" in got and "corridor_blocking" not in got
    assert "destination_closed_low_fl" in got          # aerodrome NOTAM ignores FL


def test_time_window():
    late = cases(run(etd_utc=ETD + timedelta(days=3), eta_utc=ETA + timedelta(days=3)))
    assert set(late) == {"permanent"}                  # only the PERM NOTAM is still valid
    early = cases(run(etd_utc=datetime(2026, 11, 1, 6, tzinfo=timezone.utc),
                      eta_utc=datetime(2026, 11, 1, 8, tzinfo=timezone.utc)))
    assert "expired" in early


def test_reverse_direction_same_result():
    assert set(cases(run(src="VABB", dst="VIDP"))) == set(cases(run()))


def test_sorted_by_severity_then_distance():
    sev = [f["properties"]["severity"] for f in run()["features"]]
    order = {"BLOCKING": 0, "RESTRICTIVE": 1, "ADVISORY": 2}
    assert sev == sorted(sev, key=order.get)


def test_contract_shape():
    result = run()
    assert result["type"] == "FeatureCollection"
    assert result["metadata"]["disclaimer"].startswith("Decision support for research only")
    for f in result["features"]:
        props = f["properties"]
        for key in ("severity", "category", "lower_fl", "upper_fl", "valid_during", "e_text"):
            assert key in props
        assert set(props["valid_during"]) >= {"start", "end"}
        assert f["geometry"] is None or f["geometry"]["type"] == "Polygon"


def test_eta_estimated_from_distance_and_tas():
    result = run(eta_utc=None)
    meta = result["metadata"]
    assert meta["eta_estimated"] and meta["tas_kt"] == 450
    expected = ETD + timedelta(hours=meta["route_distance_nm"] / 450)
    assert abs(datetime.fromisoformat(meta["eta_utc"].replace("Z", "+00:00")) - expected) < timedelta(seconds=1)
    assert estimate_eta(ETD, 450, 450) == ETD + timedelta(hours=1)


def test_seed_file_mode():
    result = relevant_notams_from_file(FIXTURE, "VIDP", "VABB", ETD, ETA, 0, 350, 200)
    assert result["metadata"]["count"] == 5


@pytest.mark.parametrize("kw", [
    dict(src="KJFK"), dict(dst="VIDP"), dict(etd_utc=datetime(2026, 11, 5, 6)),
    dict(eta_utc=ETD - timedelta(minutes=1)), dict(fl_lo=300, fl_hi=100),
    dict(corridor_nm=0), dict(eta_utc=ETD + timedelta(hours=30)), dict(etd_utc="not a date"),
])
def test_invalid_queries(kw):
    with pytest.raises(RetrievalError):
        run(**kw)


def test_unknown_airport():
    with pytest.raises(UnknownAirport):
        run(dst="VOZZ")


def test_point_to_arc_geometry():
    # point on the segment, beyond an end, and abeam
    assert point_to_arc_nm(10, 0, 0, 0, 20, 0) < 1e-6
    assert abs(point_to_arc_nm(25, 0, 0, 0, 20, 0) - 300.2) < 0.5      # 5 deg past B
    assert abs(point_to_arc_nm(10, 1, 0, 0, 20, 0) - 59.1) < 0.3       # 1 deg of longitude at 10N
