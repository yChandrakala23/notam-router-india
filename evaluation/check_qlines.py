"""
ICAO NOTAM Q-line parser.

Supports Q-lines such as:

Q) VOMF/QWMLW/IV/BO/W/000/999/

and Q-lines containing coordinates/radius:

Q)VECF/QWLLW/IV/NBO/W /005/050/2213N08046E015
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


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


Q_LINE_PATTERN = re.compile(
    r"""
    Q\)\s*
    (?P<fir>[A-Z]{4})
    /
    (?P<q_code>Q[A-Z]{4})
    /
    (?P<traffic>[A-Z]{2})
    /
    (?P<purpose>[A-Z]{2,3})
    /
    (?P<scope>[A-Z])
    \s*
    /
    (?P<lower_fl>\d{3})
    /
    (?P<upper_fl>\d{3})
    (?:/
        (?P<geometry>
            \d{4}[NS]\d{5}[EW]\d{3}
        )
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _parse_coordinate(
    coordinate: str,
) -> tuple[float, float]:
    """Parse compact ICAO coordinate + return latitude/longitude."""

    lat_deg = int(coordinate[0:2])
    lat_min = int(coordinate[2:4])
    lat_dir = coordinate[4].upper()

    lon_deg = int(coordinate[5:8])
    lon_min = int(coordinate[8:10])
    lon_dir = coordinate[10].upper()

    latitude = lat_deg + lat_min / 60.0
    longitude = lon_deg + lon_min / 60.0

    if lat_dir == "S":
        latitude *= -1

    if lon_dir == "W":
        longitude *= -1

    return latitude, longitude


def parse_q_line(text: str) -> QLine | None:
    """Parse the first Q-line found in a NOTAM."""

    match = Q_LINE_PATTERN.search(text.upper())

    if not match:
        return None

    data = match.groupdict()

    latitude = None
    longitude = None
    radius_nm = None

    geometry = data["geometry"]

    if geometry:
        latitude, longitude = _parse_coordinate(geometry)
        radius_nm = float(geometry[-3:])

    return QLine(
        fir=data["fir"].upper(),
        q_code=data["q_code"].upper(),
        traffic=data["traffic"].upper(),
        purpose=data["purpose"].upper(),
        scope=data["scope"].upper(),
        lower_fl=int(data["lower_fl"]),
        upper_fl=int(data["upper_fl"]),
        latitude=latitude,
        longitude=longitude,
        radius_nm=radius_nm,
    )