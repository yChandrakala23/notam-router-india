
from datetime import datetime, timezone

from ingestion.autorouter_adapter import (
    GARMIN_SCALE,
    OPEN_ENDED_SENTINEL,
    decode_coordinate,
    normalize_notam,
    timestamp_to_utc,
)


def test_garmin_coordinate_conversion():
    assert round(227871875 * GARMIN_SCALE, 6) == 19.1
    assert round(869333195 * GARMIN_SCALE, 6) == 72.866667


def test_invalid_coordinate_returns_none():
    assert decode_coordinate(None) is None
    assert decode_coordinate("unknown") is None


def test_timestamp_conversion():
    value = 1739277960
    expected = datetime.fromtimestamp(
        value, tz=timezone.utc
    ).isoformat()

    assert timestamp_to_utc(value) == expected


def test_open_ended_timestamp():
    assert timestamp_to_utc(OPEN_ENDED_SENTINEL) is None


def test_normalization_preserves_replacement_and_q_fields():
    raw = {
        "id": 123,
        "type": "R",
        "series": "A",
        "number": 1154,
        "year": 26,
        "referredseries": "A",
        "referrednumber": 714,
        "referredyear": 26,
        "fir": "VABF",
        "code23": "OB",
        "code45": "CE",
        "traffic": "IV",
        "purpose": "M",
        "scope": "AE",
        "lower": 0,
        "upper": 4,
        "lat": 227871875,
        "lon": 869333195,
        "radius": 1,
        "nelat": None,
        "nelon": None,
        "swlat": None,
        "swlon": None,
        "startvalidity": 1739277960,
        "endvalidity": OPEN_ENDED_SENTINEL,
        "estimation": "EST",
        "itema": ["VABB"],
        "iteme": "TEST NOTAM",
        "suppressed": False,
    }

    result = normalize_notam(raw)

    assert result["source_id"] == 123
    assert result["candidate_q_code"] == "QOBCE"
    assert result["referred_number"] == 714
    assert result["end_validity_utc"] is None
    assert result["end_validity_open_ended"] is True
    assert result["validity_estimation"] == "EST"
    assert result["lower_fl_source"] == 0
    assert result["upper_fl_source"] == 4
    assert result["item_e"] == "TEST NOTAM"
