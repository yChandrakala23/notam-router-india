# pgAdmin screenshots for the DBMS section

Open pgAdmin, then go to **Servers → (your PostgreSQL 14) → Databases → notam → Query Tool**. Open `db/sql/pgadmin_queries.sql` and run one block at a time: select the block, then press F5.

Take every screenshot **from your own database**. If a query returns zero rows, say so in the report; don't stage a result.

| # | Query | What to capture | What it demonstrates | Expected output format |
|---|---|---|---|---|
| S1 | Q1 | `version()`, `PostGIS_Full_Version()`, extension list | Platform choice (§2); PostgreSQL 14 + PostGIS works without upgrading | 1 text row each; `postgis`, `plpgsql` (and `pgrouting` if installed) in the list |
| S2 | Q2 | `schema_migrations` | Versioned, repeatable migrations (§14) | 3 rows: `001_init_schema`, `002_notam_pipeline`, `003_reference_rows_minimal` |
| S3 | Q3, plus the pgAdmin tree with Tables expanded | Table list + row counts | All 12 v2 tables exist (§5) | `table_name`, `approx_rows` |
| S4 | Q4 | `notam_event` constraints | Integrity rules (§8) | `conname`, `contype` (p/f/u/c), definition |
| S5 | Q5 | Index list | GiST and expression indexes (§11, §18) | Look for `notam_event_geog_idx … gist ((geom)::geography)` |
| S6 | Q6 | Ingestion runs | Run logging, idempotency (a second run shows `records_duplicate` > 0 and `records_inserted` = 0) | One row per adapter run |
| S7 | Q7 | Freshness view | Freshness monitor (SHOULD item) | One row per source; `is_stale` true/false |
| S8 | Q8 | Raw rows by source/format/status | Raw store volume; 500+ target; PARSED vs FAILED | `name`, `raw_format`, `parse_status`, `count` |
| S9 | Q9 | Raw rows by location | P1 checkpoint ("raw NOTAMs by location") | Top 25 ICAO locations |
| S10 | Q10 | FAILED rows | Malformed NOTAMs logged, not crashed | Expect the real AAI record with `C) …1390` (minute 90) |
| S11 | Q11 (three result grids) | Severity × category, geometry source, classifier method | Merged classifier output stored in the DB (§6) | Counts |
| S12 | Q12, then click the eye icon on the `geom` column (Geometry Viewer) | Circles on the map | Q-line → PostGIS circle (§12) | `area_ratio` close to 1 (slightly below) |
| S13 | Q13 | Validity counts | Every stored geometry is valid, SRID 4326 | `total = valid = srid_4326` |
| S14 | Q14 + Geometry Viewer | Methodology formula on its own | `ST_Buffer(point::geography, r·1852)` | Polygon; `area_nm2` vs `circle_area_nm2` |
| S15 | Q15 (rolled back) | R/C rows and the function result | NOTAMR/NOTAMC lifecycle (§16) | `linked`/`replaced`/`cancelled` counts |
| S16 | Q16 | Range operators | `tstzrange` / `int4range` overlap (§13) | Boolean columns |
| S17 | Q17 (edit the ETD to a time your data covers) | Relevant NOTAMs DEL–BOM | Retrieval (§17) with `match_reason`, `distance_nm` | Sorted BLOCKING → ADVISORY |
| S18 | `EXPLAIN (ANALYZE, BUFFERS)` + Q17 | Bottom lines of the plan | Query cost and time (§18) | "Execution Time: … ms" |
| S19 | Q19 | Identities with several observations | Normalisation: raw (N) vs event (1) (§9) | `nof`, `notam_id`, `observations` |
| S20 | Browser: `http://127.0.0.1:8000/docs` → GET `/notams/relevant` → Try it out | JSON response | The A→B interface | GeoJSON FeatureCollection with `metadata.query_ms` |
| S21 | Terminal: `python -m evaluation.retrieval_db_check` | Printed table | SQL ≡ reference; runtime < 500 ms | Markdown table |

Also include the ER diagram (`docs/person_a/er_diagram.png`) as a figure.
