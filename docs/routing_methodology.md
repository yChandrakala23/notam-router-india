# Routing methodology: graph, candidates, NOTAM conflicts, selection

*Research decision-support prototype; not certified and not for operational use.*

In the 9 Nov project the routing modules (`routing/`, `static_data/`) and `POST /plan` were one-line stubs. They are implemented here. Results come from `python -m evaluation.routing_eval`, run on 17 Nov 2026 against the PostGIS test database loaded from the repository snapshot.

## 1. Pipeline

```
src, dst, ETD, cruise FL, TAS
  │
  ├─ graph            routing/graph.py       DB airway graph (waypoint/airway_edge) if loaded,
  │                                          else synthetic lateral-offset lattice
  ├─ candidates       routing/candidates.py  Yen's K-shortest simple paths (K=10) + direct great circle
  ├─ relevant NOTAMs  api/relevance.py       PostGIS: validity ∩ window, FL ∩ [0, cruise], within corridor
  │                                          (corridor widened to cover the widest candidate)
  ├─ conflict check   routing/conflicts.py   per route × NOTAM: space + vertical profile + time
  └─ selection        routing/select.py      shortest feasible; tie → fewer warnings; ≤ 2 alternatives
                                             → POST /plan (api/routers/plan.py); optional persistence
                                               in route_request / candidate_route / route_conflict
```

## 2. Candidate graph

**No curated ATS airway data is loaded.** The `waypoint` and `airway_edge` tables are empty, so the planner currently uses a **synthetic lattice**:

- stations along the great circle about every 120 NM;
- each station offset laterally by 0, ±50, ±100 and ±150 NM;
- edges between neighbouring stations whose offsets differ by at most 50 NM;
- plus the direct route.

Node ids start with `SYN`, and results carry `graph_source = "synthetic_lattice"` and a note. These are not real airways or fixes. They model lateral alternatives so the NOTAM logic can be exercised and evaluated.

When real airway data is loaded into `waypoint`/`airway_edge`, `build_graph` uses it automatically, connecting the airports to waypoints within 60 NM. This is covered by tests on synthetic rows. `python -m static_data.build_graph` exports the corridor graphs as GeoJSON.

`static_data/load_airports.py` (OurAirports CSV) and `static_data/load_fir.py` (FIR GeoJSON) load reference data from files you download. Nothing is fetched automatically.

## 3. Conflict semantics

A NOTAM classified BLOCKING does not block a route by itself. For each route and each relevant NOTAM, three things are checked:

| Axis | Test |
|---|---|
| Space | Route sampled every 2 NM. A point is inside if within the circle radius (geodesic), or inside the polygon. |
| Vertical | The aircraft's FL *while inside the area*, from a simple profile: climb and descent at 3 FL/NM (≈300 ft/NM), capped at cruise. Overlaps the NOTAM band; unknown limits are unbounded. |
| Time | The time inside the area (ETD + along-track / TAS, ±15 min) overlaps the NOTAM validity. D) schedules are not parsed, so the whole B)–C) window is used. |

| Outcome | When | Effect |
|---|---|---|
| HARD | BLOCKING and all three axes overlap | route rejected, with a readable reason |
| WARNING | RESTRICTIVE / ADVISORY and all three overlap | route kept, warning attached |
| CLEARED | route enters the area but is clear vertically or in time; or overflies an aerodrome whose NOTAM concerns only that aerodrome | explanation only |
| AIRPORT_BLOCKING / AIRPORT_WARNING | facility / runway / procedure / obstacle / navaid NOTAM at the source or destination, in force at departure or arrival | status AIRPORT_UNAVAILABLE: no route choice fixes it |
| UNLOCALISED | activity NOTAM (NAV_WARNING / AIRSPACE_RESTRICTION) with no known area | reported for manual review; never rejects |

**Corrections made during the audit, all covered by tests:**

1. **En-route aerodrome closures no longer reject overflights.** Real case: "AD CLSD" at VOVZ / VOTV, with no FL band. The methodology says aerodrome closure is "BLOCKING at source/destination".
2. **AAI activities no longer get a misleading aerodrome circle.** AAI lists SHAR rocket-launch NOTAMs under the "CHENNAI VOMM" heading. They used to get a 5 NM circle around Chennai airport, which is the wrong place, and also made Chennai look closed. They are now FIR-level and reported as UNLOCALISED.
3. **AAI obstacle and procedure notices** that have only a default aerodrome circle are treated as local to that aerodrome.

## 4. Selection

- **Feasible** means no HARD conflict.
- The best route is the shortest feasible one. Routes within 0.5 NM of each other are ranked by fewer warnings. Up to two alternatives are returned.
- Every route reports:
  - distance, extra distance versus the great circle (NM and %), estimated time and ETA;
  - warnings, its full conflict list, and its geometry.
- `why_best` explains the choice.
- If nothing is feasible, the status is `NO_FEASIBLE_ROUTE`, with all rejection reasons and a suggestion per blocking NOTAM (change the cruise level or the departure time).

## 5. Results

### 5.1 Designed conflict cases (SYNTHETIC NOTAMs, DEL–BOM)

**12/12 correct: 4/4 correct rejections, 0/8 false rejections.**

| Case | Expected outcome |
|---|---|
| Blocking area on track, inside the FL band | direct route rejected; an alternative 23 NM longer chosen |
| Same area, aircraft above it | no rejection |
| Same area, NOTAM expired | no rejection |
| Same area, RESTRICTIVE | warning only |
| Area 300 NM off track | no conflict |
| SFC–FL050 area, aircraft at cruise or already climbed through | no rejection |
| SFC–FL100 area 10 NM after departure | rejected (aircraft climbing through FL017–042) |
| Destination closed | AIRPORT_UNAVAILABLE |
| Restricted area over the destination | NO_FEASIBLE_ROUTE |
| En-route aerodrome closed | no rejection |
| Corridor-wide wall | NO_FEASIBLE_ROUTE, with suggestions |

### 5.2 Real NOTAMs, five corridors, ETD 2026-10-16 22:00Z, FL350 and FL150

All ten runs returned status OK with 10/10 feasible candidates. The best route was the direct great circle (extra distance ≤ 0.01 %), and there were no HARD conflicts. Median planning time was 31–196 ms. Full table: `evaluation/results/routing_eval.md`.

So, on this snapshot, no relevant real NOTAM blocks these corridors at these times. That is a property of the data: most AAI NOTAMs are aerodrome notices, the Q-line NOTAMs come from autorouter for six airports only, and there are no airspace restrictions with real geometry. The rejection logic is therefore demonstrated by the designed cases, not by real-world blocking events.

## 6. Limitations

- **Synthetic lattice, not ATS airways.** Distances and alternatives are illustrative.
- **Coarse geometry.** Q-line circles over-approximate areas; AAI NOTAMs have no area at all.
- **Simplified vertical profile.** No SID/STAR, step climbs or performance model.
- **Schedules ignored.** D) schedules are not parsed, so NOTAMs count as active for their whole validity.
- **FIR-wide activities can't be placed** without E-line coordinates, so they become manual-review items.
- **No real HARD conflicts** occurred in the evaluated real-data window.
