"""Export the candidate-route graph for the five test corridors as GeoJSON.

    python -m static_data.build_graph [--out evaluation/results/corridor_graphs.geojson]

Uses the database airway graph when waypoint/airway_edge hold data, otherwise
the synthetic lateral-offset lattice (routing/graph.py; node ids SYN...).  The
file is for inspection on a map and for the report; planning builds the graph
on the fly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from db.reference_airports import IATA_TO_ICAO_CORRIDORS, TEST_CORRIDORS, reference_airports
from routing.graph import build_graph


def corridor_features(airports=None, conn=None) -> list[dict]:
    airports = airports or reference_airports()
    feats = []
    for a, b in TEST_CORRIDORS:
        s = {**airports[IATA_TO_ICAO_CORRIDORS[a]], "icao": IATA_TO_ICAO_CORRIDORS[a]}
        d = {**airports[IATA_TO_ICAO_CORRIDORS[b]], "icao": IATA_TO_ICAO_CORRIDORS[b]}
        G = build_graph(s, d, conn)
        for u, v, e in G.edges(data=True):
            nu, nv = G.nodes[u], G.nodes[v]
            feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
                [nu["lon"], nu["lat"]], [nv["lon"], nv["lat"]]]},
                "properties": {"corridor": f"{a}-{b}", "from": u, "to": v, "dist_nm": round(e["weight"], 1),
                               "graph_source": G.graph.get("graph_source")}})
    return feats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="evaluation/results/corridor_graphs.geojson")
    args = ap.parse_args(argv)
    feats = corridor_features()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    print(f"wrote {len(feats)} edges to {args.out}")


if __name__ == "__main__":
    main()
