"""autorouter JSON -> ICAO text -> parser (synthetic record, real field layout)."""

from parsing.autorouter_record import canonical_json, parse_autorouter_record, render_icao_text

RECORD = {
    "id": 1, "nof": "VABB", "series": "A", "number": 1154, "year": 26, "type": "R",
    "referredseries": "A", "referrednumber": 714, "referredyear": 26,
    "fir": "VABF", "code23": "OB", "code45": "CE", "traffic": "IV", "purpose": "M ",
    "scope": "AE ", "lower": 0, "upper": 4, "lat": 227871875, "lon": 869333195, "radius": 1,
    "startvalidity": 1739277960, "endvalidity": 2147483647, "estimation": None,
    "itema": ["VABB"], "itemd": None, "iteme": "SYNTHETIC TEST NOTAM", "itemf": None, "itemg": None,
}


def test_render_and_parse_round_trip():
    text = render_icao_text(RECORD)
    assert text.startswith("A1154/26 NOTAMR A0714/26")
    parsed = parse_autorouter_record(RECORD)
    assert parsed.ok
    q = parsed.qline
    assert (q.fir, q.q_code, q.traffic, q.purpose, q.scope) == ("VABF", "QOBCE", "IV", "M", "AE")
    assert (q.lower_fl, q.upper_fl, q.radius_nm) == (0, 4, 1.0)
    assert abs(q.latitude - 19.1) < 1 / 60 and abs(q.longitude - 72.8667) < 1 / 60
    assert parsed.is_permanent and parsed.locations == ["VABB"]
    assert parsed.replaces_notam_id == "A0714/26"


def test_bad_json_is_reported():
    assert not parse_autorouter_record("{not json").ok


def test_canonical_json_is_stable():
    assert canonical_json(RECORD) == canonical_json(dict(reversed(list(RECORD.items()))))
