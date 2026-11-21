# Database Design and Implementation (Person A — DBMS section)

*NOTAM-Aware Route Planning for Indian Airspace. Decision support for research only; not for operational use.*

> **About the numbers in this section.** Figures marked **[sandbox]** come from running the code on the repository's data snapshot, without a database. Figures marked **[to fill]** must come from your own PostgreSQL/PostGIS instance: run the queries in `db/sql/pgadmin_queries.sql` and copy the real output. Do not report a number you have not observed.

---

## 1. Database objectives

1. **Keep every NOTAM exactly as received** (raw store) so that parsing and classification can be re-run later without fetching again.
2. **Make ingestion idempotent.** Fetching the same NOTAM again must not create a new row.
3. **Hold one structured, classified event per NOTAM**, with its validity window, flight-level band and area geometry.
4. **Apply the NOTAMR (replace) and NOTAMC (cancel) lifecycle** so that superseded notices are never returned.
5. **Answer the relevance query** ("which NOTAMs matter for SRC→DST, ETD–ETA, FL band?") inside the database, using spatial, time-range and integer-range operators backed by indexes, in under 500 ms.
6. **Record provenance and freshness** (which source, which run, when, with what outcome).
7. **Share one schema with Person B.** Person B's routing tables (`waypoint`, `airway_edge`, `route_request`, `candidate_route`, `route_conflict`) reference `notam_event` and `airport`.

## 2. Why PostgreSQL + PostGIS

| Requirement | PostgreSQL/PostGIS feature used |
|---|---|
| Area geometry and distance on the Earth | `geometry(Polygon,4326)`, `geography` casts, `ST_Buffer`, `ST_DWithin`, `ST_Distance` (geodesic on WGS-84) |
| Validity windows with open ends (`PERM`) | `tstzrange` with an unbounded upper end, `&&` overlap operator |
| Flight-level bands | `int4range` generated column, `&&` operator |
| Fast spatial and range search | GiST indexes, including an expression index on `geom::geography` |
| Integrity | FKs, `UNIQUE`, `CHECK`, `NOT NULL`, triggers |
| Lifecycle logic close to the data | PL/pgSQL function `resolve_notam_lifecycle()` |
| Routing (Person B) | pgRouting is available but optional; B may use NetworkX |

A document store or a plain relational DB without spatial types would have to compute circle-versus-route distances in application code, and those queries could not be indexed.

**Version compatibility.** The methodology names PostgreSQL 16, and `docker-compose.yml` uses the `pgrouting/pgrouting:16-…` image. Your local Windows instance is **PostgreSQL 14 + PostGIS (port 5433)**. Every feature used here is available in PostgreSQL ≥ 12 with PostGIS 3:

| Feature | Needs |
|---|---|
| Generated column | PostgreSQL 12 |
| `EXECUTE FUNCTION` triggers | PostgreSQL 11 |
| `ADD COLUMN IF NOT EXISTS` | PostgreSQL 9.6 |

So no upgrade or downgrade is needed. pgRouting is wrapped in an exception handler: if it is missing, migration 001 prints a NOTICE and carries on.

## 3. Architecture

```
 AAI PDFs / autorouter / FAA / ICAO
          │  adapters (ingestion/*.py, one interface)
          ▼
 data_source ─< ingestion_run ─< raw_notam            (append-only, content_hash UNIQUE)
                                     │  ingestion/process.py: parse → classify
                                     ▼
                                notam_event ──< route_conflict (Person B)
                                  │   ▲
                                  │   └─ replaces_event_id (self-FK, NOTAMR/C)
                                  ├─> fir ──< airport ──< route_request ─< candidate_route
                                  ▼
               relevance SQL (api/relevance.py) → GET /notams/relevant → Person B /plan
```

The layers are:

- **Raw layer:** `data_source`, `ingestion_run`, `raw_notam`
- **Structured layer:** `notam_event`
- **Reference layer:** `fir`, `airport`
- **Routing layer (Person B):** `waypoint`, `airway`, `airway_edge`, `route_request`, `candidate_route`, `route_conflict`

## 4. ER diagram

- Source: `docs/person_a/er_diagram.mmd` (Mermaid)
- Rendered image: `docs/person_a/er_diagram.png`

To regenerate the image: `mmdc -i er_diagram.mmd -o er_diagram.png`, or paste the source into https://mermaid.live.

Key relationships:

- `data_source 1–N ingestion_run 1–N raw_notam`
- `raw_notam 1–N notam_event` (the event points to the *best* raw observation)
- `notam_event 0..1–N notam_event` (a NOTAMR/C event replaces at most one earlier event)
- `fir 1–N airport`, `fir 1–N notam_event`
- `notam_event 1–N route_conflict N–1 candidate_route N–1 route_request N–1 airport`

## 5. Relational schema (Person A tables, after migrations 001 + 002)

```
data_source(source_id PK, name UNIQUE NOT NULL, access_type, active, base_url,
            poll_interval_min, created_at)
ingestion_run(run_id PK, source_id FK→data_source NOT NULL, started_at NOT NULL, finished_at,
              status, records_fetched, records_inserted, records_duplicate, records_failed,
              error_message, trigger)
raw_notam(raw_id PK, run_id FK→ingestion_run NOT NULL, notam_id, nof, raw_text NOT NULL,
          raw_format, source_url, location_hint, fetched_at NOT NULL,
          content_hash UNIQUE NOT NULL, parse_status, parse_error, parsed_at)
notam_event(event_id PK, raw_id FK→raw_notam NOT NULL, nof, notam_id, UNIQUE(nof, notam_id),
            series, notam_number, notam_year, action, replaces_event_id FK→notam_event,
            replaces_notam_id, lifecycle_status, fir_code FK→fir, icao_location,
            q_code, traffic, purpose, scope, lower_fl, upper_fl,
            fl_range GENERATED, valid_during NOT NULL, center, geom, radius_nm, geom_source,
            is_permanent, end_estimated, schedule_text, e_text,
            category, severity, classifier_conf, classifier_method, source_rank,
            created_at, updated_at)
fir(icao_code PK, name, boundary)
airport(icao_code PK, iata_code, name, city, fir_code FK→fir, location)
```

## 6. Table descriptions

| Table | Purpose | Written by |
|---|---|---|
| `data_source` | One row per feed (`AAI_AIM_INDIA`, `AUTOROUTER`, `FAA_NOTAM_API`, `ICAO_API`) | `ingestion.store.ensure_source` |
| `ingestion_run` | One row per adapter execution: counts, status, redacted error | `ingestion.scheduler` |
| `raw_notam` | Unchanged source payload: ICAO text, AAI PDF block, or autorouter JSON | `ingestion.store.store_raw` |
| `notam_event` | Parsed, classified, geo-referenced NOTAM; one row per NOTAM identity | `ingestion.process` |
| `fir`, `airport` | Reference data. Migration 003 inserts minimal rows; Person B's loaders supersede them | 003 + Person B |
| `schema_migrations` | Migration bookkeeping (version, checksum, time) | `db/migrate.py` |
| Views `v_source_freshness`, `v_active_notam` | Freshness monitor; active NOTAMs | migration 002 |

## 7. Primary and foreign keys

- **Surrogate keys** (`SERIAL`/`BIGSERIAL`) everywhere except `fir` and `airport`, which use the natural ICAO code.
- **Natural key of a NOTAM:** `(nof, notam_id)`, enforced as `notam_event_identity_uq`. The NOTAM number alone is not unique, because Delhi and Mumbai can both issue `A0100/26`. In the AAI data, 962 distinct ids correspond to 1,128 distinct (office, id) pairs **[sandbox]**.
- **Foreign keys:**
  - `ingestion_run.source_id`
  - `raw_notam.run_id`
  - `notam_event.raw_id`
  - `notam_event.replaces_event_id` (self-reference)
  - `notam_event.fir_code`
  - `airport.fir_code`
  - Person B's `route_conflict.event_id`

## 8. Constraints (migration 002)

| Constraint | Rule |
|---|---|
| `notam_event_action_ck` | `action IN ('N','R','C')` |
| `notam_event_lifecycle_ck` | `ACTIVE / REPLACED / CANCELLED` |
| `notam_event_severity_ck` | `BLOCKING / RESTRICTIVE / ADVISORY` |
| `notam_event_category_ck` | the 8 classifier categories |
| `notam_event_fl_ck` | 0 ≤ FL ≤ 999 and lower ≤ upper |
| `notam_event_validity_ck` | range not empty, lower bound present (a NOTAM must have a B) time) |
| `notam_event_geom_valid_ck` | `ST_IsValid(geom)` |
| `notam_event_id_format_ck` | `^[A-Z][0-9]{4}/[0-9]{2}$` |
| `notam_event_no_self_replace_ck` | an event cannot replace itself |
| `raw_notam_hash_ck` | 64 hex characters |
| `raw_notam_format_ck`, `raw_notam_parse_status_ck` | enumerations |
| `ingestion_run_status_ck`, `ingestion_run_times_ck` | status enumeration; finish ≥ start |
| `data_source_access_type_ck`, `data_source_name_uq` | enumeration; unique name |

The column types also act as constraints:

- `geometry(Polygon,4326)` rejects wrong geometry types and SRIDs.
- `tstzrange` forces every time to UTC-comparable `timestamptz`.

## 9. Normalisation

- **1NF.** All attributes are atomic. Ranges (`tstzrange`, `int4range`) and geometries are single typed values with their own operators, not repeating groups.
- **2NF.** Every table has a single-column surrogate PK, so there are no partial dependencies. In `notam_event`, the identity `(nof, notam_id)` is a candidate key, and all other attributes depend on the whole of it.
- **3NF.** The source of a raw row is *not* stored in `raw_notam`; it is derived through `run_id → ingestion_run.source_id`, which avoids a transitive dependency.
- **Raw vs structured split.** One NOTAM can appear in several observations: the same AAI NOTAM is repeated in successive monthly summaries, and the same NOTAM can arrive from AAI and from autorouter. Observations go in `raw_notam` (1–N). The NOTAM itself goes in `notam_event`, which points to the best observation (`source_rank`: sources with a Q-line rank above AAI summaries).
- **Deliberate redundancy (documented).**

  | Column | Why it is kept |
  |---|---|
  | `fl_range` | Generated from `lower_fl`/`upper_fl`. It cannot drift because it is `GENERATED ALWAYS … STORED`; it exists only so it can be GiST-indexed. |
  | `center` | Derivable from the Q-line, but stored so the circle can be rebuilt and displayed. |
  | `e_text` | Copied from the raw text so retrieval needs no re-parsing. |

  None of these break 3NF semantics: each is a function of the row's own key.

## 10. Core SQL

**Idempotent raw insert** (`ingestion/store.py`):

```sql
INSERT INTO raw_notam (run_id, notam_id, nof, raw_text, raw_format, source_url,
                       location_hint, fetched_at, content_hash)
VALUES (...)
ON CONFLICT (content_hash) DO NOTHING
RETURNING raw_id;          -- no row returned  ⇒ duplicate
```

**Event upsert with source priority and PostGIS circle** (`ingestion/process.py`, abridged):

```sql
INSERT INTO notam_event (..., valid_during, center, geom, ...)
VALUES (...,
  tstzrange(:valid_from, :valid_until, '[]'),
  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
  ST_Buffer(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_nm * 1852.0)::geometry,
  ...)
ON CONFLICT ON CONSTRAINT notam_event_identity_uq DO UPDATE SET ...
WHERE notam_event.source_rank < EXCLUDED.source_rank
   OR (notam_event.source_rank = EXCLUDED.source_rank AND notam_event.raw_id <= EXCLUDED.raw_id);
```

The relevance query is given in §17. All report queries are in `db/sql/pgadmin_queries.sql` (Q1–Q19).

## 11. Spatial indexing

| Index | Type | Used by |
|---|---|---|
| `notam_event_geom_idx` | GiST (`geom`) | Person B's `ST_Intersects(route, geom)` |
| `notam_event_geog_idx` | GiST (`(geom::geography)`) expression | `ST_DWithin(geom::geography, route, m)` in retrieval |
| `fir_boundary_idx`, `airport_location_idx`, `airway_edge_geom_idx` | GiST | FIR crossing, airport lookup, graph |

**Why the expression index?** Retrieval measures distances in metres on the ellipsoid, so it casts to `geography`. A plain index on `geom` cannot serve a predicate on `geom::geography`. An index on that exact expression can.

## 12. PostGIS geometry operations

| Operation | Where | Meaning |
|---|---|---|
| `ST_Buffer(point::geography, r·1852)::geometry` | event insert | Q-line circle of *r* NM (methodology formula) |
| `ST_Buffer(airport.location::geography, 5·1852)` | AAI records | default 5 NM aerodrome circle (`AERODROME_DEFAULT`) |
| `ST_MakeLine(src, dst)::geography` | retrieval | great-circle route (geodesic in geography) |
| `ST_DWithin(geom::geography, route, corridor_m)` | retrieval | NOTAM area within the corridor half-width |
| `ST_Distance(...)/1852` | retrieval output | distance from route, in NM |
| `ST_IsValid`, `ST_SRID`, `ST_Area(geography)` | checks | validity, SRID, area ≈ πr² |

Each geography buffer is a 32-segment polygon. Its area is slightly below πr², because the polygon is inscribed in the circle. Q14 in the query pack prints the ratio. For the 737 stored circles the area ratio is 0.9923–0.9944 **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]**.

## 13. Validity and flight-level range queries

- **Validity.** `valid_during tstzrange '[]'`. `PERM` gives an unbounded upper end. `EST` uses the stated end, and `end_estimated = true` is kept for display.
- **Overlap.** `valid_during && tstzrange(:etd, :eta, '[]')` is inclusive at both ends. It is served by the GiST index on `valid_during`, plus a partial GiST index on active, non-cancel rows.
- **Flight levels.** `fl_range && int4range(:fl_lo, :fl_hi, '[]')`. A NULL limit becomes an unbounded end. This happens for AAI summaries, which carry no Q-line, so the comparison errs on the conservative side.

## 14. Migrations

| File | Content | Re-runnable |
|---|---|---|
| `001_init_schema.sql` | Shared v2 schema (methodology §4); now `IF NOT EXISTS`; pgRouting optional | yes |
| `002_notam_pipeline.sql` | Person A columns, constraints, indexes, trigger, `resolve_notam_lifecycle()`, views | yes (`ADD COLUMN IF NOT EXISTS`; constraint helper checks `pg_constraint`) |
| `003_reference_rows_minimal.sql` | 4 FIRs and 30 aerodromes, `ON CONFLICT DO NOTHING` | yes; never overwrites Person B's rows |
| `004_classifier_explanation.sql` | `classifier_reason`, `classifier_keyword`, `classifier_uncertainty TEXT[]` on `notam_event` | yes (`ADD COLUMN IF NOT EXISTS`) |

`python -m db.migrate` applies pending files in order, one transaction each, and records them in `schema_migrations` with a checksum. `--check` is a read-only diagnostic: it reports server version, extensions and tables, and never prints the password.

Both files were applied **twice** to a PostgreSQL 16 server without errors **[sandbox, using a test-only PostGIS stand-in]**. Run them on PostGIS for the definitive check.

## 15. Ingestion and storage

- **Adapters** implement `SourceAdapter.fetch() → list[RawNotam]` and never touch the DB.
- **`ingestion.scheduler`** does the following for each adapter:
  1. Upsert `data_source`.
  2. Open an `ingestion_run` (RUNNING).
  3. Fetch.
  4. `store_raw` in one transaction.
  5. Close the run as SUCCESS, PARTIAL, FAILED or SKIPPED, with counts and a redacted error.

  After all adapters, `process_pending` parses and classifies new raw rows.
- **Failure handling.** A failing source does not stop the others. A malformed NOTAM sets `raw_notam.parse_status = 'FAILED'` with the reason in `parse_error`; it does not crash the run.
- **Content hash.**
  - AAI blocks: hashed after removing PDF page furniture, so the same NOTAM repeated in later monthly summaries collapses. 1,647 blocks become 1,135 unique raw records **[sandbox]**.
  - autorouter: canonical JSON.
  - ICAO text: whitespace-normalised.
- **Polling.** `--loop --interval 15` polls every 15 minutes, or use Windows Task Scheduler with `--once`. The AAI adapter throttles itself to one fetch per 24 h, because the summaries are monthly documents.

## 16. NOTAM lifecycle (NOTAMR / NOTAMC)

`resolve_notam_lifecycle()` runs after every processing batch.

1. **Link.** Each R or C event whose `replaces_event_id` is still NULL gets linked to the event with the same `nof` and `notam_id = replaces_notam_id`.
2. **Cancel.** Any event referenced by a C becomes `CANCELLED`.
3. **Replace.** Any still-active event referenced by an R becomes `REPLACED`.

Notes:

- **Late arrivals.** References that cannot be resolved yet stay unlinked and are retried on the next run. This handles a replacement that arrives before the original.
- **NOTAMR stays active.** A NOTAMR is *itself* active, even when its predecessor is unknown. It is the current version, so excluding it would hide a live notice. The earlier in-memory filter treated such records as unresolved and dropped them; that was corrected here.
- **Verified behaviour [sandbox, synthetic NOTAMs]:**
  - N `A9001/26`, then R `A9002/26` → A9001 becomes REPLACED.
  - Then C `A9003/26` → A9002 becomes CANCELLED.
  - A malformed Q-line (FL300 above FL100) is stored as FAILED.

## 17. Relevant-NOTAM retrieval

Implemented in `api/relevance.py` (`RELEVANT_SQL`); exposed as `relevant_notams(...)` and `GET /notams/relevant`.

```sql
WITH params AS (SELECT tstzrange(:etd, :eta, '[]') win, int4range(:fl_lo, :fl_hi, '[]') fl,
                       :corridor_nm * 1852.0 corridor_m),
     route  AS (SELECT ST_MakeLine(s.location, d.location)::geography gc, s.fir_code src_fir, d.fir_code dst_fir
                  FROM airport s, airport d WHERE s.icao_code = :src AND d.icao_code = :dst),
     route_firs AS (... FIRs whose boundary is within the corridor, plus src/dst FIRs ...)
SELECT ... FROM notam_event n, route r, params p
 WHERE n.lifecycle_status = 'ACTIVE' AND n.action IS DISTINCT FROM 'C'
   AND n.valid_during && p.win
   AND (    n.icao_location IN (:src, :dst)
        OR (n.fl_range && p.fl
            AND (   (n.geom IS NOT NULL AND ST_DWithin(n.geom::geography, r.gc, p.corridor_m))
                 OR (n.geom IS NULL AND n.geom_source = 'FIR_WIDE' AND n.fir_code IN (SELECT * FROM route_firs)))));
```

**Changes from the methodology's sketch query, and why:**

| Sketch | Implementation | Reason |
|---|---|---|
| `ST_DWithin(geom::geography, corridor::geography, 0)` with a buffered corridor | `ST_DWithin(geom::geography, line::geography, corridor_m)` | Same set; no buffer polygon to build; uses the geography GiST index |
| FL overlap required for every NOTAM | Not required for source/destination aerodrome NOTAMs | The aircraft passes FL000 → cruise there; otherwise a runway or aerodrome closure at FL000–005 would be missed |
| `action <> 'C'` | `lifecycle_status='ACTIVE' AND action IS DISTINCT FROM 'C'` | Also drops replaced/cancelled events; NULL-safe |
| — | FIR-wide clause | AAI FIR-level NOTAMs and Q-lines with radius 999 have no circle |

**ETA.** If `eta` is not given, ETA = ETD + great-circle distance / TAS (default TAS 450 kt).

**Ordering.** Results are sorted by severity, then by distance from the route.

## 18. Indexing and query optimisation

- Every retrieval predicate has an index: GiST on `geom::geography`, GiST on `valid_during` (partial on active rows), GiST on `fl_range`, B-tree on `icao_location` and `fir_code`.
- The route line is computed once, in a CTE.
- `ST_DWithin` is index-assisted, unlike `ST_Distance(...) < x`.
- `EXPLAIN (ANALYZE, BUFFERS)` on Q17 shows the real plan and execution time **[to fill from your pgAdmin screenshot]**.

With about 1.3k events a sequential scan may still be the cheapest plan, and that is the correct planner choice at this size. The indexes matter as the table grows with 15-minute polling.

Optional Redis caching (`api/cache.py`) keys results by query parameters plus a data version: the latest `run_id` and the latest event `updated_at`. Each ingestion cycle therefore invalidates stale answers.

**Target:** < 500 ms per corridor. Measured median 17–25 ms (max 35 ms) across the five corridors on 1,245 events **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]**. Re-measure on your PostgreSQL 14 for the report.

## 19. Testing and validation

| Test | Result |
|---|---|
| `pytest` (unit + DB-URL tests; no DB needed) | 124 passed, 1 skipped |
| `tests/test_db_integration.py` (live PostGIS, rolled-back transaction) | 5 passed **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]** |
| Migrations applied twice (idempotency) | OK, no errors **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]** |
| Offline ingestion of the real snapshot | 1,790 fetched → 1,278 raw inserted, 512 duplicates; 1,277 parsed, 1 malformed logged; 1,245 events; 9 NOTAMR links → 9 REPLACED. Re-run: 0 inserted **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]** |
| Geometry validity of stored circles | 737 / 737 valid, SRID 4326, Polygon **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]** |
| SQL vs Python-reference retrieval, 5 corridors | 100 % agreement on 4 corridors; BOM–MAA 7 extra SQL rows, all one aerodrome (VOML) at 199.78 NM on the spheroid, i.e. corridor-edge, 0 unexplained **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]** |
| `GET /notams/relevant` live (uvicorn) | 200 / 422 / 404 behave as specified; Redis cache miss → hit → miss after a new ingestion run **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]** |
| pgAdmin query pack (`db/sql/pgadmin_queries.sql`) | all blocks execute without error **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]** |

The integration tests check four things:

- the methodology buffer produces a valid 4326 polygon with the correct area;
- SQL retrieval returns exactly the 5 expected synthetic cases;
- `resolve_notam_lifecycle()` works;
- the CHECK constraints reject a bad severity and an inverted FL band.

## 20. Limitations and future improvements

- **Coarse geometry.** Q-line circles over-approximate the real area (E-line polygons are not extracted; stretch goal).
- **Schedules ignored.** D-line schedules are not used, so a NOTAM is treated as active for its whole B–C period.
- **AAI summaries lack data.** They have no Q-line (no FL band, no centre), and their aerodrome comes from PDF section headings. The first section of each PDF has no heading in the extracted text, so its location is unknown: about 6% of records **[sandbox]**.
- **FIR-wide fallback.** Without Person B's FIR boundaries, FIR-wide NOTAMs are matched only through the source/destination FIRs.
- **NOTAM identity for ICAO-text feeds** (FAA/ICAO) has no issuing office, so it is namespaced as `UNK-<FIR>`. Cross-source deduplication with AAI and autorouter is therefore not guaranteed for those feeds.
- **Partitioning.** `raw_notam` grows with 15-minute polling. Future work: partition by `fetched_at` month, and archive events whose validity ended long ago.
- **Future improvements:**
  - exclusion constraints, so the same NOTAM identity cannot be active twice in one time range;
  - row-level security for the commercial autorouter rows;
  - pgRouting in-database conflict checks.
