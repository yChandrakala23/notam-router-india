"""Route selection and end-to-end planning in seed mode (SYNTHETIC NOTAMs)."""

from routing.planner import plan_route
from tests.routing_helpers import BOM, ETD, feat


def test_clean_case_selects_direct_route():
    r = plan_route("VIDP", "VABB", ETD, 350, notam_features=[])
    assert r["status"] == "OK" and r["best_route"]["is_direct"] and r["best_route"]["extra_distance_nm"] == 0
    assert len(r["alternatives"]) == 2 and r["feasible_count"] == r["candidates_evaluated"]
    assert r["disclaimer"].startswith("Decision support for research only")


def test_blocking_on_track_selects_alternative_with_reasons():
    r = plan_route("VIDP", "VABB", ETD, 200, notam_features=[feat()])
    assert r["status"] == "OK" and not r["best_route"]["is_direct"]
    assert r["best_route"]["extra_distance_nm"] > 0
    rej = [x for x in r["rejected_routes"] if x["is_direct"]][0]
    assert not rej["is_feasible"] and rej["reject_reason"].startswith("Crosses Z0001/26")
    assert "rejected for HARD conflicts" in r["why_best"]
    eta_min = r["best_route"]["est_time_min"]
    assert abs(eta_min - r["best_route"]["distance_nm"] / 450 * 60) < 0.1


def test_same_notam_above_cruise_does_not_reject():
    r = plan_route("VIDP", "VABB", ETD, 350, notam_features=[feat()])
    assert r["best_route"]["is_direct"] and not r["rejected_routes"]


def test_no_feasible_route_gives_suggestions():
    r = plan_route("VIDP", "VABB", ETD, 200, notam_features=[feat(r=250, hi=300)])
    assert r["status"] == "NO_FEASIBLE_ROUTE" and r["best_route"] is None
    assert r["suggestions"] and "cruise level" in r["suggestions"][0]
    assert len(r["rejected_routes"]) == r["candidates_evaluated"]


def test_airport_unavailable():
    f = feat(category="AERODROME", reason="AERODROME", loc="VABB", lat=BOM["lat"], lon=BOM["lon"], r=5)
    r = plan_route("VIDP", "VABB", ETD, 350, notam_features=[f])
    assert r["status"] == "AIRPORT_UNAVAILABLE" and r["airport_blocking"]


def test_tie_break_by_fewer_warnings():
    from routing.candidates import CandidateRoute
    from routing.conflicts import Conflict
    from routing.select import select_route

    a = CandidateRoute(1, ["A", "B"], [(0, 0), (0, 1)], 100.0, "t")
    b = CandidateRoute(2, ["A", "C", "B"], [(0, 0), (0.1, 0.5), (0, 1)], 100.2, "t")
    a.conflicts = [Conflict(1, "N1", "WARNING", "RESTRICTIVE", "X", "w")]
    res = select_route([a, b], etd=ETD, tas_kt=450, gc_nm=100.0, cruise_fl=350)
    assert res["best_route"]["route_id"] == 2


def test_invalid_inputs():
    import pytest

    from api.relevance import RetrievalError, UnknownAirport

    with pytest.raises(RetrievalError):
        plan_route("VIDP", "VABB", ETD, 0, notam_features=[])
    with pytest.raises(UnknownAirport):
        plan_route("VIDP", "VOZZ", ETD, 350, notam_features=[])
