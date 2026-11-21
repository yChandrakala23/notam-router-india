# Interface Contract (Person A <-> Person B)

*Decision support for research only; not for operational use.*

## 1. Python function (in-process, recommended for `POST /plan`)

```python
from api.relevance import relevant_notams

fc = relevant_notams(
    src="VIDP", dst="VABB",
    etd_utc=datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc),
    eta_utc=None,          # None -> ETD + great-circle distance / tas_kt
    fl_lo=0, fl_hi=350,    # flight levels; aerodrome NOTAMs at src/dst ignore the FL band
    corridor_nm=200,       # half-width; methodology 150-300
    tas_kt=450,
    include_raw=False,     # True adds properties.raw_text (autorouter rendered as ICAO text)
    connection=None,       # optional SQLAlchemy Connection (e.g. B's transaction)
)
```

Errors:

- `api.relevance.RetrievalError` — invalid input (HTTP 422)
- `api.relevance.UnknownAirport` — src/dst not in `airport` (HTTP 404)

Seed mode, with no database: `relevant_notams_from_file("tests/fixtures/synthetic_notam_events.json", "VIDP", "VABB", etd, eta, 0, 350, 200)` returns the same output format (the events in that file are SYNTHETIC).

## 2. HTTP

```
GET /notams/relevant?src=VIDP&dst=VABB&etd=2026-11-05T06:00:00Z[&eta=...][&fl_lo=0]&fl_hi=350[&corridor_nm=200][&tas_kt=450][&include_raw=false]
GET /notams/freshness
```

Status codes:

| Code | Meaning |
|---|---|
| 200 | OK |
| 422 | Invalid query |
| 404 | Unknown airport |
| 503 | Database unavailable |

## 3. Output (GeoJSON FeatureCollection)

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature", "id": 812,
    "geometry": {"type": "Polygon", "coordinates": [[[77.0, 28.91], ...]]},
    "properties": {
      "event_id": 812, "notam_id": "A0123/26", "nof": "VIDP", "action": "N",
      "severity": "BLOCKING", "category": "AIRSPACE_RESTRICTION", "q_code": "QRTCA",
      "icao_location": "VIDP", "fir_code": "VIDF",
      "lower_fl": 0, "upper_fl": 250,
      "valid_during": {"start": "2026-11-05T00:00:00Z", "end": "2026-11-30T23:59:00Z",
                       "end_estimated": false, "permanent": false},
      "radius_nm": 25.0, "geom_source": "QLINE_CIRCLE",
      "match_reason": "CORRIDOR", "distance_nm": 0.0,
      "e_text": "...", "schedule_text": null,
      "classifier_conf": 1.0, "classifier_method": "RULES"
    }
  }],
  "metadata": {"src": "VIDP", "dst": "VABB", "etd_utc": "...", "eta_utc": "...", "eta_estimated": true,
               "route_distance_nm": 614.6, "fl_lo": 0, "fl_hi": 350, "corridor_nm": 200,
               "count": 1, "counts_by_severity": {"BLOCKING": 1, "RESTRICTIVE": 0, "ADVISORY": 0},
               "query_ms": 12.3, "engine": "postgis", "cache": "miss", "disclaimer": "..."}
}
```

### Field semantics for the conflict check (Person B)

**`severity`**

| Value | Meaning |
|---|---|
| `BLOCKING` | HARD conflict if the route intersects `geometry` and the FL bands overlap |
| `RESTRICTIVE` / `ADVISORY` | WARNING |

**`match_reason`**

| Value | Meaning |
|---|---|
| `AERODROME` | The NOTAM concerns src/dst. A BLOCKING one here (e.g. aerodrome closed) is reported to the user: no route can avoid it |
| `CORRIDOR` | Polygon within `corridor_nm` of the great-circle route |
| `FIR_WIDE` | No geometry; applies to a FIR the route uses. Treat it as a warning unless BLOCKING |

**`geometry`**

- A `null` geometry means "no area known". This applies to FIR-wide NOTAMs, and to AAI aerodrome NOTAMs whose aerodrome is missing from `airport`.
- Use `ST_Intersects` only when geometry is not null.

**Missing or open values**

| Field | When null | Treat as |
|---|---|---|
| `lower_fl` / `upper_fl` | Source has no Q-line (AAI summaries) | Unbounded |
| `valid_during.end` | `PERM` | Open-ended |

D) schedules are not applied: a NOTAM counts as active for its whole B–C window.

**Ordering:** BLOCKING, then RESTRICTIVE, then ADVISORY; within each, nearest first.

## 4. Schema

Shared v2 tables (`db/migrations/001_init_schema.sql`). Person A's extensions are in `002_notam_pipeline.sql`, and minimal FIR/airport rows in `003_reference_rows_minimal.sql` (`ON CONFLICT DO NOTHING`; B's loaders may UPSERT over them). `route_conflict.event_id` references `notam_event.event_id`.

## 5. Labels

`category` and `severity` values come from `classification/taxonomy.py` (8 categories, 3 severities). The same values are enforced by the database CHECK constraints and used by the API and the routing logic. Any display layer must use these values unchanged.

Each feature also carries the classifier's explanation:

- `classifier_reason`
- `classifier_keyword` (the keyword-guard match, if any)
- `classifier_uncertainty` (a list of reasons)
- `center_lat` / `center_lon` (circle centre, used by the conflict check)

## 6. `POST /plan` (implemented: `api/routers/plan.py`, `routing/`)

```
POST /plan {"src": "VIDP", "dst": "VABB", "etd": "2026-11-05T06:00:00Z", "fl": 350,
            "tas_kt": 450, "k": 10, "persist": false}
```

**Response:**

- `status`: OK | NO_FEASIBLE_ROUTE | AIRPORT_UNAVAILABLE
- `best_route` and up to two `alternatives`. Each route has: distance, extra distance vs great circle, est_time_min, eta_utc, warnings, its `conflicts` list (each with an explanation) and `geometry` (a GeoJSON LineString).
- `why_best`
- `rejected_routes`, with `reject_reason`
- `airport_blocking`
- `suggestions` (only when nothing is feasible)
- `relevant_notams`: the FeatureCollection above
- `graph_source`, `runtime_ms`, `disclaimer`

Conflict semantics are documented in `docs/routing_methodology.md`: BLOCKING rejects a route only when space, flight level and time all overlap.
