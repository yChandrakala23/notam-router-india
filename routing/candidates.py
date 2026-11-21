"""Candidate route generation: Yen's K-shortest simple paths (methodology layer 5).

``networkx.shortest_simple_paths`` implements Yen's algorithm.  The direct
great-circle route is always included (it is an edge of the synthetic lattice;
for an airway graph it is added explicitly).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import islice

import networkx as nx

from routing.geo import gc_distance_nm, path_length_nm


@dataclass
class CandidateRoute:
    route_id: int
    nodes: list[str]
    points: list[tuple[float, float]]       # (lat, lon)
    distance_nm: float
    graph_source: str
    is_direct: bool = False
    conflicts: list = field(default_factory=list)

    def linestring(self) -> dict:
        return {"type": "LineString", "coordinates": [[round(lon, 6), round(lat, 6)] for lat, lon in self.points]}


def k_shortest_routes(G: nx.Graph, src: str, dst: str, k: int = 10) -> list[CandidateRoute]:
    if src not in G or dst not in G:
        raise ValueError(f"{src} or {dst} not in route graph")
    source = G.graph.get("graph_source", "unknown")
    routes: list[CandidateRoute] = []
    seen: set[tuple[str, ...]] = set()
    try:
        paths = list(islice(nx.shortest_simple_paths(G, src, dst, weight="weight"), k))
    except nx.NetworkXNoPath:
        paths = []
    direct = [src, dst]
    if tuple(direct) not in {tuple(p) for p in paths}:
        paths.append(direct)
    for path in paths:
        key = tuple(path)
        if key in seen:
            continue
        seen.add(key)
        pts = [(G.nodes[n]["lat"], G.nodes[n]["lon"]) for n in path]
        routes.append(CandidateRoute(len(routes) + 1, list(path), pts, round(path_length_nm(pts), 1),
                                     source if path != direct or G.has_edge(src, dst) else "direct",
                                     is_direct=(path == direct)))
    routes.sort(key=lambda r: r.distance_nm)
    for i, r in enumerate(routes, start=1):
        r.route_id = i
    return routes


def great_circle_nm(src: dict, dst: dict) -> float:
    return gc_distance_nm(src["lat"], src["lon"], dst["lat"], dst["lon"])
