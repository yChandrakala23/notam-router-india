"""ICAO NOTAM parser: Q-line (with circle geometry), A), B), C), D), E), F), G).

Owner: Person A (Data & NOTAM Intelligence).

Supported Q-line shapes (all seen in real Indian NOTAMs)::

    Q) VIDF/QRTCA/IV/BO/AW/000/250/2830N07700E025
    Q) VOMF/QWMLW/IV/BO/W/000/999/          (no centre/radius)
    Q)VECF/QWLLW/IV/NBO/W /005/050/2213N08046E015
    Q) VECF/QPICH/I/NBO/A/000/999/2239N08827E005  (1-letter traffic/scope)

Geometry
--------
The methodology builds the NOTAM area in PostGIS with
``ST_Buffer(point::geography, radius_nm * 1852)::geometry``.  The database
loader (``ingestion/process.py``) does exactly that.  This module also offers a
pure-Python geodesic circle (``circle_polygon``) so that the parser, the seed
mode and the unit tests work without a database.  Both use WGS-84 lon/lat
(SRID 4326).

Validity
--------
* B) and C) are ``YYMMDDHHMM`` in UTC.
* ``C) PERM`` -> open-ended (``valid_until = None``, ``is_permanent = True``).
* ``C) ... EST`` -> the stated time is used as the end (methodology v2) and
  ``end_estimated = True`` is recorded.
* D) schedules are kept as text only; the NOTAM is treated as active for the
  whole B)-C) period (conservative, methodology v2).

Research prototype; not for operational use.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

EARTH_RADIUS_NM = 3440.065  # mean Earth radius in nautical miles
NM_TO_M = 1852.0

# Q-line radius 999 means "whole FIR / not a meaningful circle".
FIR_WIDE_RADIUS_NM = 999


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------


@dataclass
class QLine:
    fir: str
    q_code: str
    traffic: str
    purpose: str
    scope: str
    lower_fl: int
    upper_fl: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_nm: Optional[float] = None

    @property
    def subject(self) -> str:
        """2nd+3rd letters of the NOTAM code (e.g. 'RT' in QRTCA)."""
        return self.q_code[1:3]

    @property
    def condition(self) -> str:
        """4th+5th letters of the NOTAM code (e.g. 'CA' in QRTCA)."""
        return self.q_code[3:5]

    @property
    def has_circle(self) -> bool:
        return (
            self.latitude is not None
            and self.longitude is not None
            and self.radius_nm is not None
        )

    @property
    def is_fir_wide(self) -> bool:
        return self.radius_nm is not None and self.radius_nm >= FIR_WIDE_RADIUS_NM


@dataclass
class ParsedNotam:
    """Structured result of parsing one ICAO-format NOTAM."""

    notam_id: Optional[str] = None          # e.g. A1234/26
    series: Optional[str] = None
    number: Optional[int] = None
    year: Optional[int] = None
    action: Optional[str] = None            # N, R or C
    replaces_notam_id: Optional[str] = None  # reference in NOTAMR / NOTAMC
    qline: Optional[QLine] = None
    locations: list[str] = field(default_factory=list)   # A) item(s)
    valid_from: Optional[datetime] = None   # B)
    valid_until: Optional[datetime] = None  # C) (None = PERM / open)
    is_permanent: bool = False
    end_estimated: bool = False
    schedule: Optional[str] = None          # D) raw text, not interpreted
    e_text: Optional[str] = None            # E)
    lower_limit: Optional[str] = None       # F) raw
    upper_limit: Optional[str] = None       # G) raw
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def icao_location(self) -> Optional[str]:
        return self.locations[0] if self.locations else None

    @property
    def ok(self) -> bool:
        """Minimum needed to create a notam_event row."""
        return not self.errors and self.valid_from is not None


# --------------------------------------------------------------------------
# Q-line
# --------------------------------------------------------------------------

# Lenient on whitespace and on the 1-3 letter traffic/purpose/scope fields,
# strict on the code, the flight levels and the coordinate block.
Q_LINE_PATTERN = re.compile(
    r"""
    Q\)\s*
    (?P<fir>[A-Z]{4})\s*/\s*
    (?P<q_code>Q[A-Z]{4})\s*/\s*
    (?P<traffic>[IVK](?:\s?[IVK])?)\s*/\s*
    (?P<purpose>[NBOMK](?:\s?[NBOMK]){0,2})\s*/\s*
    (?P<scope>[AEWK](?:\s?[AEWK])?)\s*/\s*
    (?P<lower_fl>\d{3})\s*/\s*
    (?P<upper_fl>\d{3})
    (?:\s*/\s*
        (?P<geometry>\d{4}\s?[NS]\s?\d{5}\s?[EW]\s?\d{3})?
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)


class QLineError(ValueError):
    """Raised for a Q-line that is present but internally invalid."""


def _parse_coordinate(coordinate: str) -> tuple[float, float]:
    """Parse ``DDMM[NS]DDDMM[EW]`` -> (latitude, longitude) in degrees."""
    coordinate = coordinate.replace(" ", "").upper()

    lat_deg = int(coordinate[0:2])
    lat_min = int(coordinate[2:4])
    lat_dir = coordinate[4]
    lon_deg = int(coordinate[5:8])
    lon_min = int(coordinate[8:10])
    lon_dir = coordinate[10]

    if lat_min >= 60 or lon_min >= 60:
        raise QLineError(f"Minutes out of range in {coordinate!r}")
    if lat_deg > 90 or lon_deg > 180:
        raise QLineError(f"Degrees out of range in {coordinate!r}")

    latitude = lat_deg + lat_min / 60.0
    longitude = lon_deg + lon_min / 60.0
    if lat_dir == "S":
        latitude = -latitude
    if lon_dir == "W":
        longitude = -longitude
    return latitude, longitude


def parse_q_line(text: str, *, strict: bool = False) -> QLine | None:
    """Parse the first Q-line found in ``text``.

    Returns None when there is no Q-line.  When a Q-line is present but has
    impossible values (minutes >= 60, lower FL > upper FL) it returns None, or
    raises :class:`QLineError` if ``strict`` is True.
    """
    match = Q_LINE_PATTERN.search(text.upper())
    if not match:
        return None

    data = match.groupdict()
    try:
        lower_fl = int(data["lower_fl"])
        upper_fl = int(data["upper_fl"])
        if lower_fl > upper_fl:
            raise QLineError(
                f"Lower FL {lower_fl:03d} is above upper FL {upper_fl:03d}"
            )

        latitude = longitude = radius_nm = None
        geometry = data["geometry"]
        if geometry:
            geometry = geometry.replace(" ", "")
            latitude, longitude = _parse_coordinate(geometry[:11])
            radius_nm = float(geometry[11:14])
    except QLineError:
        if strict:
            raise
        return None

    def _clean(value: str) -> str:
        return value.replace(" ", "").upper()

    return QLine(
        fir=data["fir"].upper(),
        q_code=data["q_code"].upper(),
        traffic=_clean(data["traffic"]),
        purpose=_clean(data["purpose"]),
        scope=_clean(data["scope"]),
        lower_fl=lower_fl,
        upper_fl=upper_fl,
        latitude=latitude,
        longitude=longitude,
        radius_nm=radius_nm,
    )


def format_q_line(q: QLine) -> str:
    """Render a QLine back to ICAO text (used for autorouter records)."""
    geo = ""
    if q.has_circle:
        lat, lon = q.latitude, q.longitude
        lat_total = round(abs(lat) * 60)
        lon_total = round(abs(lon) * 60)
        geo = (
            f"{lat_total // 60:02d}{lat_total % 60:02d}{'N' if lat >= 0 else 'S'}"
            f"{lon_total // 60:03d}{lon_total % 60:02d}{'E' if lon >= 0 else 'W'}"
            f"{int(round(q.radius_nm)):03d}"
        )
    return (
        f"Q) {q.fir}/{q.q_code}/{q.traffic}/{q.purpose}/{q.scope}/"
        f"{q.lower_fl:03d}/{q.upper_fl:03d}/{geo}"
    )


# --------------------------------------------------------------------------
# Geometry (pure Python; PostGIS does the same with ST_Buffer on geography)
# --------------------------------------------------------------------------


def destination_point(
    lat: float, lon: float, bearing_deg: float, distance_nm: float
) -> tuple[float, float]:
    """Great-circle destination point on a sphere. Returns (lat, lon)."""
    phi1 = math.radians(lat)
    lam1 = math.radians(lon)
    theta = math.radians(bearing_deg)
    delta = distance_nm / EARTH_RADIUS_NM

    phi2 = math.asin(
        math.sin(phi1) * math.cos(delta)
        + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    )
    lam2 = lam1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    lon2 = (math.degrees(lam2) + 540) % 360 - 180
    return math.degrees(phi2), lon2


def circle_polygon(
    lat: float, lon: float, radius_nm: float, segments: int = 64
) -> dict:
    """GeoJSON Polygon approximating a geodesic circle (counter-clockwise)."""
    if radius_nm <= 0:
        raise ValueError("radius_nm must be positive")
    ring = []
    for i in range(segments):
        bearing = 360.0 - (360.0 * i / segments)  # CCW exterior ring
        p_lat, p_lon = destination_point(lat, lon, bearing, radius_nm)
        ring.append([round(p_lon, 6), round(p_lat, 6)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def polygon_to_wkt(polygon: dict) -> str:
    ring = polygon["coordinates"][0]
    pts = ", ".join(f"{x} {y}" for x, y in ring)
    return f"POLYGON(({pts}))"


def qline_geometry(q: QLine, min_radius_nm: float = 1.0) -> dict | None:
    """GeoJSON circle for a Q-line, or None for no-centre / FIR-wide Q-lines."""
    if not q.has_circle or q.is_fir_wide:
        return None
    return circle_polygon(q.latitude, q.longitude, max(q.radius_nm, min_radius_nm))


# --------------------------------------------------------------------------
# Date / validity
# --------------------------------------------------------------------------


def parse_notam_datetime(value: str) -> datetime:
    """Parse ``YYMMDDHHMM`` (UTC) -> aware datetime.

    Two-digit years: 00-49 -> 20xx, 50-99 -> 19xx.  ``2400`` is not valid in
    ICAO NOTAMs (2359 is used) and is rejected.
    """
    value = value.strip()
    if not re.fullmatch(r"\d{10}", value):
        raise ValueError(f"Invalid NOTAM datetime: {value}")

    year = int(value[0:2])
    year += 2000 if year < 50 else 1900
    return datetime(
        year,
        int(value[2:4]),
        int(value[4:6]),
        int(value[6:8]),
        int(value[8:10]),
        tzinfo=timezone.utc,
    )  # raises ValueError for month 13, hour 24, ...


_B_PATTERN = re.compile(r"(?<![A-Z(])B\)\s*(\d{10})", re.IGNORECASE)
_C_PATTERN = re.compile(
    r"(?<![A-Z(])C\)\s*(PERM|\d{10})\s*(EST)?", re.IGNORECASE
)


def parse_validity(text: str) -> tuple[datetime | None, datetime | None]:
    """Extract B) and C) validity. Returns (valid_from, valid_until).

    ``valid_until`` is None for ``PERM`` or a missing C).
    """
    normalized = " ".join(line.strip() for line in text.splitlines())
    b_match = _B_PATTERN.search(normalized)
    c_match = _C_PATTERN.search(normalized)

    valid_from = parse_notam_datetime(b_match.group(1)) if b_match else None
    valid_until = None
    if c_match and c_match.group(1).upper() != "PERM":
        valid_until = parse_notam_datetime(c_match.group(1))
    return valid_from, valid_until


# --------------------------------------------------------------------------
# Full NOTAM
# --------------------------------------------------------------------------

HEADER_PATTERN = re.compile(
    r"""
    (?P<id>(?P<series>[A-Z])(?P<number>\d{4})/(?P<year>\d{2}))
    \s+NOTAM(?P<action>[NRC])
    (?:\s+(?P<ref>[A-Z]\d{4}/\d{2}))?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Item markers must not be preceded by a letter or '(' so that E-text
# enumerations such as "(A) RWY LIGHTS" or "RWY 09B)" are not mistaken.
_ITEM = r"(?<![A-Z0-9(])"
_A_PATTERN = re.compile(_ITEM + r"A\)\s*((?:[A-Z]{4}\b\s*)+)")
_A_STOP_WORDS = {"PART"}
_D_PATTERN = re.compile(_ITEM + r"D\)\s*(.*?)\s*(?=" + _ITEM + r"E\))", re.S)
_E_PATTERN = re.compile(_ITEM + r"E\)\s*(.*)", re.S)
_FG_PATTERN = re.compile(
    r"\s" + _ITEM + r"F\)\s*(?P<f>\S+(?:\s?(?:FT|M)\s?(?:AMSL|AGL)?)?)"
    r"\s+G\)\s*(?P<g>\S+(?:\s?(?:FT|M)\s?(?:AMSL|AGL)?)?)\s*$",
    re.S,
)


def parse_notam(text: str) -> ParsedNotam:
    """Parse a complete ICAO-format NOTAM into :class:`ParsedNotam`.

    Never raises for bad input: problems are collected in ``errors`` (fatal
    for event creation) or ``warnings`` (event can still be created).
    """
    result = ParsedNotam()
    if not text or not text.strip():
        result.errors.append("empty text")
        return result

    upper = text.upper().replace("\r", "")

    header = HEADER_PATTERN.search(upper)
    if header:
        result.notam_id = header.group("id")
        result.series = header.group("series")
        result.number = int(header.group("number"))
        result.year = int(header.group("year"))
        result.action = header.group("action")
        result.replaces_notam_id = header.group("ref")
        if result.action in ("R", "C") and not result.replaces_notam_id:
            result.warnings.append(
                f"NOTAM{result.action} without a referenced NOTAM id"
            )
    else:
        result.errors.append("missing NOTAM id / NOTAMN|R|C header")

    try:
        result.qline = parse_q_line(upper, strict=True)
    except QLineError as exc:
        result.errors.append(f"invalid Q-line: {exc}")
    if result.qline is None and "Q)" in upper and not any(
        e.startswith("invalid Q-line") for e in result.errors
    ):
        result.warnings.append("Q) present but not in a recognised format")

    a_match = _A_PATTERN.search(upper)
    if a_match:
        # "A) VOMF PART 1 OF 3" -> ["VOMF"]; "A) VIDP VABB" -> both.
        for token in a_match.group(1).split():
            if token in _A_STOP_WORDS:
                break
            result.locations.append(token)

    flat = " ".join(line.strip() for line in upper.splitlines())
    b_match = _B_PATTERN.search(flat)
    c_match = _C_PATTERN.search(flat)
    if b_match:
        try:
            result.valid_from = parse_notam_datetime(b_match.group(1))
        except ValueError as exc:
            result.errors.append(f"invalid B): {exc}")
    else:
        result.errors.append("missing B) start of validity")

    if c_match:
        end_value = c_match.group(1).upper()
        if end_value == "PERM":
            result.is_permanent = True
        else:
            try:
                result.valid_until = parse_notam_datetime(end_value)
            except ValueError as exc:
                result.errors.append(f"invalid C): {exc}")
            result.end_estimated = bool(c_match.group(2))
    elif result.action != "C":
        result.warnings.append("missing C): treated as open-ended")

    if (
        result.valid_from
        and result.valid_until
        and result.valid_until < result.valid_from
    ):
        result.errors.append("C) end of validity precedes B) start")

    d_match = _D_PATTERN.search(upper)
    if d_match:
        result.schedule = " ".join(d_match.group(1).split()) or None

    e_match = _E_PATTERN.search(upper)
    if e_match:
        body = e_match.group(1)
        fg = _FG_PATTERN.search(body)
        if fg:
            result.lower_limit = fg.group("f").strip()
            result.upper_limit = fg.group("g").strip()
            body = body[: fg.start()]
        result.e_text = " ".join(body.split()) or None
    else:
        result.warnings.append("missing E) text")

    if result.qline and not result.locations:
        result.warnings.append("missing A) location")

    return result
