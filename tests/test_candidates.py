"""Graph construction and Yen's K-shortest candidates."""

import networkx as nx

from routing.candidates import great_circle_nm, k_shortest_routes
from routing.graph import airway_graph_from_rows, attach_airports, synthetic_corridor_graph
from tests.routing_helpers import BOM, DEL

S = {**DEL, "icao": "VIDP"}
D = {**BOM, "icao": "VABB"}


def test_synthetic_lattice_is_labelled_and_connected():
    G = synthetic_corridor_graph(S, D)
    assert G.graph["graph_source"] == "synthetic_lattice"
    assert nx.has_path(G, "VIDP", "VABB") and G.has_edge("VIDP", "VABB")
    assert all(n.startswith("SYN") for n, d in G.nodes(data=True) if d["kind"] == "synthetic")


def test_k_shortest_sorted_unique_and_includes_direct():
    routes = k_shortest_routes(synthetic_corridor_graph(S, D), "VIDP", "VABB", k=10)
    assert len(routes) == 10 and routes[0].is_direct
    assert [r.distance_nm for r in routes] == sorted(r.distance_nm for r in routes)
    assert len({tuple(r.nodes) for r in routes}) == 10
    gc = great_circle_nm(S, D)
    assert abs(routes[0].distance_nm - gc) < 0.2 and all(r.distance_nm >= gc - 0.2 for r in routes)
    assert routes[0].linestring()["type"] == "LineString"


def test_alternatives_are_laterally_displaced():
    routes = k_shortest_routes(synthetic_corridor_graph(S, D), "VIDP", "VABB", k=10)
    assert any(any("R" in n or "L" in n for n in r.nodes[1:-1]) for r in routes[1:])


def test_airway_graph_from_rows_and_attach():
    wps = [{"ident": "ALPHA", "lat": 28.0, "lon": 76.5}, {"ident": "BRAVO", "lat": 23.8, "lon": 74.9},
           {"ident": "CHARL", "lat": 19.5, "lon": 73.2}]
    edges = [{"from": "ALPHA", "to": "BRAVO", "airway": "W1"}, {"from": "BRAVO", "to": "CHARL", "airway": "W1"}]
    G = attach_airports(airway_graph_from_rows(wps, edges), S, D, connect_nm=80)
    assert G.graph["graph_source"] == "ats_airways"
    routes = k_shortest_routes(G, "VIDP", "VABB", k=3)
    assert any(r.nodes == ["VIDP", "ALPHA", "BRAVO", "CHARL", "VABB"] for r in routes)
    assert any(r.is_direct for r in routes)
