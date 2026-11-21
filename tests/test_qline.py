
"""Q-line parser and NOTAM validity tests."""

from datetime import datetime, timezone
from pathlib import Path

from parsing.qline import (
    parse_notam_datetime,
    parse_q_line,
    parse_validity,
)


def test_parse_qline_with_geometry():
    text = (
        "Q)VECF/QWLLW/IV/NBO/W /005/050/"
        "2213N08046E015"
    )

    result = parse_q_line(text)

    assert result is not None
    assert result.fir == "VECF"
    assert result.q_code == "QWLLW"
    assert result.traffic == "IV"
    assert result.purpose == "NBO"
    assert result.scope == "W"

    assert result.lower_fl == 5
    assert result.upper_fl == 50

    assert abs(result.latitude - 22.2166667) < 1e-6
    assert abs(result.longitude - 80.7666667) < 1e-6

    assert result.radius_nm == 15


def test_parse_indian_pslv_qline():
    fixture = Path(
        "tests/fixtures/qline/pslv_c47.txt"
    )

    text = fixture.read_text(
        encoding="utf-8"
    )

    result = parse_q_line(text)

    assert result is not None
    assert result.fir == "VOMF"
    assert result.q_code == "QWMLW"
    assert result.traffic == "IV"
    assert result.purpose == "BO"
    assert result.scope == "W"

    assert result.lower_fl == 0
    assert result.upper_fl == 999

    assert result.latitude is None
    assert result.longitude is None
    assert result.radius_nm is None


def test_no_qline_returns_none():
    text = """
    A0508/20 NOTAMN

    A) VOMF
    B) 2003050945
    C) 2004031345

    E) ROCKET LAUNCH ACTIVITY.
    """

    result = parse_q_line(text)

    assert result is None


def test_parse_notam_datetime():
    result = parse_notam_datetime("1911100330")

    assert result == datetime(
        2019,
        11,
        10,
        3,
        30,
        tzinfo=timezone.utc,
    )


def test_parse_pslv_validity():
    text = """
    A2390/19 NOTAMN
    Q) VOMF/QWMLW/IV/BO/W/000/999/
    A) VOMF
    B) 1911100330
    C) 1912090530
    """

    valid_from, valid_until = parse_validity(text)

    assert valid_from == datetime(
        2019,
        11,
        10,
        3,
        30,
        tzinfo=timezone.utc,
    )

    assert valid_until == datetime(
        2019,
        12,
        9,
        5,
        30,
        tzinfo=timezone.utc,
    )


def test_parse_permanent_validity():
    text = """
    A1234/26 NOTAMN
    B) 2601010000
    C) PERM
    """

    valid_from, valid_until = parse_validity(text)

    assert valid_from == datetime(
        2026,
        1,
        1,
        0,
        0,
        tzinfo=timezone.utc,
    )

    assert valid_until is None



# ---------------------------------------------------------------------------
# Person A additions: hardened Q-line parser, full NOTAM parser, geometry
# ---------------------------------------------------------------------------

import math

import pytest

from parsing.qline import (
    QLineError,
    circle_polygon,
    format_q_line,
    parse_notam,
    qline_geometry,
)


def test_methodology_example_qline():
    q = parse_q_line("Q) VIDF/QRTCA/IV/BO/AW/000/250/2830N07700E025")
    assert (q.fir, q.q_code, q.traffic, q.purpose, q.scope) == ("VIDF", "QRTCA", "IV", "BO", "AW")
    assert (q.lower_fl, q.upper_fl) == (0, 250)
    assert (q.latitude, q.longitude, q.radius_nm) == (28.5, 77.0, 25.0)
    assert q.subject == "RT" and q.condition == "CA"


def test_one_letter_traffic_and_padded_scope():
    # real autorouter/ICAO pattern: traffic "I", scope "A" padded with spaces
    q = parse_q_line("Q) VECF/QPICH/I /NBO/A  /000/999/2239N08827E005")
    assert q is not None
    assert (q.traffic, q.purpose, q.scope) == ("I", "NBO", "A")
    assert abs(q.latitude - 22.65) < 1e-9 and abs(q.longitude - 88.45) < 1e-9


def test_southern_western_coordinates():
    q = parse_q_line("Q) FAKE/QRTCA/IV/BO/W/000/100/0300S08100W010")
    assert q.latitude == -3.0 and q.longitude == -81.0


def test_invalid_minutes_rejected():
    assert parse_q_line("Q) VIDF/QRTCA/IV/BO/W/000/100/2875N07700E010") is None
    with pytest.raises(QLineError):
        parse_q_line("Q) VIDF/QRTCA/IV/BO/W/000/100/2875N07700E010", strict=True)


def test_lower_above_upper_rejected():
    with pytest.raises(QLineError):
        parse_q_line("Q) VIDF/QRTCA/IV/BO/W/300/100/2830N07700E010", strict=True)


def test_fir_wide_radius():
    q = parse_q_line("Q) VIDF/QXXXX/IV/NBO/E/000/999/2830N07700E999")
    assert q.is_fir_wide and qline_geometry(q) is None


def test_format_q_line_round_trip():
    text = "Q) VIDF/QRTCA/IV/BO/AW/000/250/2830N07700E025"
    assert format_q_line(parse_q_line(text)) == text


def test_circle_polygon_is_closed_and_has_correct_radius():
    from api.relevance import gc_distance_nm

    poly = circle_polygon(28.5, 77.0, 25)
    ring = poly["coordinates"][0]
    assert poly["type"] == "Polygon" and ring[0] == ring[-1] and len(ring) == 65
    for lon, lat in ring[:-1]:
        assert abs(gc_distance_nm(28.5, 77.0, lat, lon) - 25) < 0.01


def test_parse_full_notam_fixture():
    parsed = parse_notam(Path("tests/fixtures/qline/pslv_c48.txt").read_text(encoding="utf-8"))
    assert parsed.ok
    assert parsed.notam_id == "A2802/19" and parsed.action == "N"
    assert parsed.locations == ["VOMF"]          # "A) VOMF PART 1 OF 3"
    assert parsed.valid_from == datetime(2019, 12, 11, 9, 30, tzinfo=timezone.utc)
    assert parsed.schedule.startswith("11 0930-1130")
    assert parsed.e_text.startswith("PSLV-C48 ROCKET LAUNCH")


SYNTHETIC_R = """A0123/26 NOTAMR A0100/26
Q) VIDF/QRTCA/IV/BO/AW/000/250/2830N07700E025
A) VIDP B) 2610010000 C) 2610312359 EST
D) DAILY 0300-1000
E) SYNTHETIC TEST. TEMPO RESTRICTED AREA ACTIVATED. (A) ITEM B) TEXT
F) SFC G) FL250"""


def test_parse_replacement_with_est_and_limits():
    p = parse_notam(SYNTHETIC_R)
    assert p.ok and p.action == "R" and p.replaces_notam_id == "A0100/26"
    assert p.end_estimated and not p.is_permanent
    assert p.valid_until == datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)
    assert p.schedule == "DAILY 0300-1000"
    # "(A) ITEM B) TEXT" inside E) must not be read as items A)/B)
    assert p.locations == ["VIDP"] and "(A) ITEM B) TEXT" in p.e_text
    assert (p.lower_limit, p.upper_limit) == ("SFC", "FL250")


def test_parse_perm():
    p = parse_notam("A0001/26 NOTAMN\nQ) VABF/QOBCE/IV/M/A/000/005/1905N07252E001\n"
                    "A) VABB B) 2601010000 C) PERM\nE) SYNTHETIC OBSTACLE")
    assert p.ok and p.is_permanent and p.valid_until is None


def test_malformed_notams_do_not_raise():
    for text in ["", "garbage", "A0001/26 NOTAMN\nB) 2613010000 C) 2601010000\nE) X",
                 "A0001/26 NOTAMN\nQ) VIDF/QRTCA/IV/BO/W/000/100/2875N07700E010\nB) 2601010000"]:
        p = parse_notam(text)
        assert not p.ok and p.errors


def test_end_before_start_is_error():
    p = parse_notam("A0001/26 NOTAMN\nA) VIDP B) 2602010000 C) 2601010000\nE) X")
    assert "C) end of validity precedes B) start" in p.errors
