
from datetime import datetime, timezone

import pytest

from api.relevance import filter_relevant_notams


ETD = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
ETA = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def make_notam(**overrides):
    notam = {
        "source_id": "SYNTHETIC-001",
        "lifecycle_status": "current_candidate",
        "start_validity_utc": "2026-10-17T09:00:00Z",
        "end_validity_utc": "2026-10-17T13:00:00Z",
        "lower_fl_source": 100,
        "upper_fl_source": 300,
        "distance_nm": 10,
        "severity": "high",
        "category": "airspace_restriction",
        "item_e": "Synthetic test notice",
        "geom": {
            "type": "Point",
            "coordinates": [77.6, 12.9],
        },
    }
    notam.update(overrides)
    return notam


def run_filter(*notams, **overrides):
    args = {
        "etd_utc": ETD,
        "eta_utc": ETA,
        "fl_lo": 150,
        "fl_hi": 250,
        "corridor_nm": 25,
    }
    args.update(overrides)

    return filter_relevant_notams(list(notams), **args)


def test_matching_notam_is_returned():
    result = run_filter(make_notam())

    assert len(result["features"]) == 1
    feature = result["features"][0]
    assert feature["properties"]["source_id"] == "SYNTHETIC-001"
    assert feature["properties"]["category"] == "airspace_restriction"


def test_notice_outside_flight_time_is_excluded():
    notam = make_notam(
        start_validity_utc="2026-10-17T13:00:00Z",
        end_validity_utc="2026-10-17T14:00:00Z",
    )

    assert run_filter(notam)["features"] == []


def test_open_ended_notice_can_overlap_flight():
    notam = make_notam(end_validity_utc=None)

    assert len(run_filter(notam)["features"]) == 1


def test_non_overlapping_altitude_is_excluded():
    notam = make_notam(
        lower_fl_source=300,
        upper_fl_source=400,
    )

    assert run_filter(notam)["features"] == []


def test_notice_outside_corridor_is_excluded():
    notam = make_notam(distance_nm=26)

    assert run_filter(notam)["features"] == []


def test_unresolved_replacement_is_excluded():
    notam = make_notam(lifecycle_status="unresolved_reference")

    assert run_filter(notam)["features"] == []


def test_missing_spatial_distance_is_excluded():
    notam = make_notam()
    notam.pop("distance_nm")

    assert run_filter(notam)["features"] == []


def test_missing_geometry_is_excluded():
    notam = make_notam(geom=None)

    assert run_filter(notam)["features"] == []


def test_invalid_time_order_is_rejected():
    with pytest.raises(ValueError):
        run_filter(make_notam(), etd_utc=ETA, eta_utc=ETD)


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        run_filter(
            make_notam(),
            etd_utc=datetime(2026, 10, 17, 10, 0),
        )


def test_invalid_altitude_range_is_rejected():
    with pytest.raises(ValueError):
        run_filter(make_notam(), fl_lo=300, fl_hi=100)
