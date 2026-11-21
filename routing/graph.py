"""Route graph for candidate generation.

Two sources, in order of preference:

1. **ATS airway graph from the database** (``waypoint`` / ``airway`` /
   ``airway_edge``, methodology layer 5).  Used when the tables hold real
   airway data.  Source/destination airports are connected to waypoints
   within ``connect_nm``.
2. **Synthetic corridor lattice** (fallback, used today because no curated
   airway data has been loaded).  Stations are placed along the great circle
   and offset laterally (default 0, +/-50, +/-100, +/-150 NM); edges join
   neighbouring stations.  Node ids start with ``SYN`` and every route built
   from it is labelled ``graph_source = "synthetic_lattice"``.  These are NOT
   real ATS routes or fixes; they model the lateral alternatives an airway
   network would offer so the NOTAM conflict logic can be exercised and
   evaluated.  Replace with curated ATS segments for operational realism.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import networkx as nx

from routing.geo import bearing_deg, destination_point, gc_distance_nm, intermediate

DEFAULT_OFFSETS_NM = (-150, -100, -50, 0, 50, 100, 150)


@dataclass(frozen=True)
class Node:
    id: str
    lat: float
    lon: float
    kind: str  # airport | waypoint | synthetic


def _add_node(G: nx.Graph, node: Node) -> None:
    G.add_node(node.id, lat=node.lat, lon=node.lon, kind=node.kind)


def _add_edge(G: nx.Graph, a: str, b: str, airway: Optional[str] = None,
              lower_fl: Optional[int] = None, upper_fl: Optional[int] = None) -> None:
    na, nb = G.nodes[a], G.nodes[b]
    G.add_edge(a, b, weight=gc_distance_nm(na["lat"], na["lon"], nb["lat"], nb["lon"]),
               airway=airway, lower_fl=lower_fl, upper_fl=upper_fl)


def synthetic_corridor_graph(src: dict, dst: dict, *, offsets_nm: Iterable[float] = DEFAULT_OFFSETS_NM,
                             stations: Optional[int] = None, max_lateral_step_nm: float = 50.0) -> nx.Graph:
    """Lattice of laterally offset waypoints between two airports.

    ``src`` / ``dst``: dicts with icao, lat, lon.  ``stations`` defaults to one
    every ~120 NM (at least 3).
    """
    G = nx.Graph(graph_source="synthetic_lattice")
    total = gc_distance_nm(src["lat"], src["lon"], dst["lat"], dst["lon"])
    n = stations or max(3, int(round(total / 120.0)))
    offsets = sorted(set(float(o) for o in offsets_nm))
    _add_node(G, Node(src["icao"], src["lat"], src["lon"], "airport"))
    _add_node(G, Node(dst["icao"], dst["lat"], dst["lon"], "airport"))

    grid: list[list[str]] = []
    for k in range(1, n + 1):
        lat0, lon0 = intermediate(src["lat"], src["lon"], dst["lat"], dst["lon"], k / (n + 1))
        track = bearing_deg(lat0, lon0, dst["lat"], dst["lon"])
        row = []
        for off in offsets:
            if off == 0:
                lat, lon = lat0, lon0
            else:
                lat, lon = destination_point(lat0, lon0, track + (90 if off > 0 else -90), abs(off))
            node_id = f"SYN{k:02d}{'R' if off > 0 else 'L' if off < 0 else 'C'}{int(abs(off)):03d}"
            _add_node(G, Node(node_id, lat, lon, "synthetic"))
            row.append((node_id, off))
        grid.append(row)

    for node_id, off in grid[0]:
        _add_edge(G, src["icao"], node_id)
    for node_id, off in grid[-1]:
        _add_edge(G, node_id, dst["icao"])
    for row_a, row_b in zip(grid, grid[1:]):
        for a, off_a in row_a:
            for b, off_b in row_b:
                if abs(off_a - off_b) <= max_lateral_step_nm + 1e-9:
                    _add_edge(G, a, b)
    _add_edge(G, src["icao"], dst["icao"], airway="DCT")  # direct great-circle route
    return G


def airway_graph_from_rows(waypoints: list[dict], edges: list[dict]) -> nx.Graph:
    """Graph from waypoint / airway_edge rows (DB or tests)."""
    G = nx.Graph(graph_source="ats_airways")
    for w in waypoints:
        _add_node(G, Node(w["ident"], w["lat"], w["lon"], "waypoint"))
    for e in edges:
        if e["from"] in G and e["to"] in G:
            _add_edge(G, e["from"], e["to"], e.get("airway"), e.get("lower_fl"), e.get("upper_fl"))
    return G


def attach_airports(G: nx.Graph, src: dict, dst: dict, connect_nm: float = 60.0) -> nx.Graph:
    """Connect src/dst airports to airway waypoints within ``connect_nm``."""
    for ap in (src, dst):
        _add_node(G, Node(ap["icao"], ap["lat"], ap["lon"], "airport"))
        near = [n for n, d in G.nodes(data=True) if d["kind"] == "waypoint"
                and gc_distance_nm(ap["lat"], ap["lon"], d["lat"], d["lon"]) <= connect_nm]
        for n in near:
            _add_edge(G, ap["icao"], n, airway="SID/STAR (simplified)")
    return G


def load_db_airway_graph(conn) -> Optional[nx.Graph]:
    """Real ATS graph from the database, or None when no airway data is loaded."""
    from sqlalchemy import text

    edges = conn.execute(text("""
        SELECT a.designator AS airway, f.ident AS "from", t.ident AS "to", e.lower_fl, e.upper_fl
          FROM airway_edge e
          JOIN waypoint f ON f.waypoint_id = e.from_waypoint_id
          JOIN waypoint t ON t.waypoint_id = e.to_waypoint_id
          LEFT JOIN airway a ON a.airway_id = e.airway_id""")).mappings().all()
    if not edges:
        return None
    waypoints = conn.execute(text(
        "SELECT ident, ST_Y(location) AS lat, ST_X(location) AS lon FROM waypoint WHERE location IS NOT NULL"
    )).mappings().all()
    return airway_graph_from_rows([dict(w) for w in waypoints], [dict(e) for e in edges])


def build_graph(src: dict, dst: dict, conn=None, **lattice_kwargs) -> nx.Graph:
    """Real airway graph when available and connected, else the synthetic lattice."""
    if conn is not None:
        G = load_db_airway_graph(conn)
        if G is not None:
            attach_airports(G, src, dst)
            if nx.has_path(G, src["icao"], dst["icao"]):
                return G
    return synthetic_corridor_graph(src, dst, **lattice_kwargs)
