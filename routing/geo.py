"""Spherical geometry helpers for routing (NM, degrees, WGS-84 lon/lat order in GeoJSON)."""

from __future__ import annotations

import math

from api.relevance import EARTH_RADIUS_NM, gc_distance_nm
from parsing.qline import destination_point


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def intermediate(lat1, lon1, lat2, lon2, fraction: float) -> tuple[float, float]:
    """Point at ``fraction`` of the great-circle segment (lat, lon)."""
    d = gc_distance_nm(lat1, lon1, lat2, lon2)
    if d == 0:
        return lat1, lon1
    return destination_point(lat1, lon1, bearing_deg(lat1, lon1, lat2, lon2), d * fraction)


def path_length_nm(points: list[tuple[float, float]]) -> float:
    return sum(gc_distance_nm(a[0], a[1], b[0], b[1]) for a, b in zip(points, points[1:]))


def sample_path(points: list[tuple[float, float]], step_nm: float = 2.0) -> list[tuple[float, float, float]]:
    """Points every ``step_nm`` along the path as (lat, lon, along_track_nm)."""
    out = [(points[0][0], points[0][1], 0.0)]
    travelled = 0.0
    for a, b in zip(points, points[1:]):
        leg = gc_distance_nm(a[0], a[1], b[0], b[1])
        n = max(1, int(math.ceil(leg / step_nm)))
        for i in range(1, n + 1):
            lat, lon = intermediate(a[0], a[1], b[0], b[1], i / n)
            out.append((lat, lon, travelled + leg * i / n))
        travelled += leg
    return out


def point_in_polygon(lat: float, lon: float, ring: list[list[float]]) -> bool:
    """Ray casting on a lon/lat ring (adequate for NOTAM-sized polygons)."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi:
            inside = not inside
        j = i
    return inside


__all__ = ["EARTH_RADIUS_NM", "gc_distance_nm", "destination_point", "bearing_deg",
           "intermediate", "path_length_nm", "sample_path", "point_in_polygon"]
