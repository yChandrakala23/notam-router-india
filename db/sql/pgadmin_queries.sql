-- pgadmin_queries.sql  -- Person A: queries for the DBMS report / screenshots
-- Run each numbered block separately in pgAdmin (Query Tool on database "notam").
-- All are read-only except Q15 (inside BEGIN ... ROLLBACK).

-- Q1  Versions and extensions (screenshot S1)
SELECT version();
SELECT PostGIS_Full_Version();
SELECT extname, extversion FROM pg_extension ORDER BY extname;

-- Q2  Applied migrations (S2)
SELECT version, applied_at FROM schema_migrations ORDER BY version;

-- Q3  Tables and row counts (S3)
SELECT relname AS table_name, n_live_tup AS approx_rows
  FROM pg_stat_user_tables ORDER BY relname;

-- Q4  Constraints on notam_event (S4)
SELECT conname, contype, pg_get_constraintdef(oid) AS definition
  FROM pg_constraint WHERE conrelid = 'notam_event'::regclass ORDER BY contype, conname;

-- Q5  Indexes on the NOTAM tables (S5)
SELECT tablename, indexname, indexdef
  FROM pg_indexes WHERE tablename IN ('raw_notam', 'notam_event', 'ingestion_run', 'data_source')
 ORDER BY tablename, indexname;

-- Q6  Ingestion runs (S6)
SELECT r.run_id, s.name, r.status, r.started_at, r.finished_at,
       r.records_fetched, r.records_inserted, r.records_duplicate, r.records_failed
  FROM ingestion_run r JOIN data_source s USING (source_id)
 ORDER BY r.run_id DESC LIMIT 20;

-- Q7  Freshness per source (S7)
SELECT name, last_status, last_success_at, minutes_since_success, is_stale FROM v_source_freshness;

-- Q8  Raw store: volume, dedup, parse outcome by source (S8)
SELECT s.name, rn.raw_format, rn.parse_status, count(*)
  FROM raw_notam rn JOIN ingestion_run r USING (run_id) JOIN data_source s USING (source_id)
 GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

-- Q9  Raw NOTAMs by location (P1 checkpoint query) (S9)
SELECT COALESCE(location_hint, '(unknown)') AS location, count(*)
  FROM raw_notam GROUP BY 1 ORDER BY 2 DESC LIMIT 25;

-- Q10 Malformed NOTAMs that were logged, not crashed (S10)
SELECT raw_id, notam_id, parse_error, left(raw_text, 80) AS raw_start
  FROM raw_notam WHERE parse_status = 'FAILED';

-- Q11 Structured events: severity x category, geometry source (S11)
SELECT severity, category, count(*) FROM notam_event GROUP BY 1, 2 ORDER BY 1, 3 DESC;
SELECT geom_source, count(*), count(geom) AS with_geometry FROM notam_event GROUP BY 1;
SELECT classifier_method, count(*), round(avg(classifier_conf)::numeric, 3) AS mean_conf
  FROM notam_event GROUP BY 1 ORDER BY 2 DESC;

-- Q12 Q-line parsing + geometry example (S12) - use pgAdmin "Geometry Viewer" on geom
SELECT event_id, nof, notam_id, q_code, lower_fl, upper_fl, radius_nm,
       ST_AsText(center) AS centre, ST_NPoints(geom) AS vertices,
       round((ST_Area(geom::geography) / (pi() * (radius_nm * 1852.0) ^ 2))::numeric, 4) AS area_ratio,
       geom
  FROM notam_event WHERE geom_source = 'QLINE_CIRCLE' ORDER BY event_id LIMIT 20;

-- Q13 Geometry validity of all stored areas (S13)
SELECT count(*) AS total, count(*) FILTER (WHERE ST_IsValid(geom)) AS valid,
       count(*) FILTER (WHERE ST_SRID(geom) = 4326) AS srid_4326
  FROM notam_event WHERE geom IS NOT NULL;

-- Q14 Methodology buffer, standalone (S14): 25 NM circle at 28 30N 077 00E
SELECT ST_AsText(ST_Centroid(g)) AS centroid, ST_NPoints(g) AS vertices,
       round((ST_Area(g::geography) / 1852.0 ^ 2)::numeric, 1) AS area_nm2,
       round((pi() * 25 ^ 2)::numeric, 1) AS circle_area_nm2, g
  FROM (SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(77.0, 28.5), 4326)::geography, 25 * 1852)::geometry AS g) t;

-- Q15 NOTAMR / NOTAMC lifecycle (S15) - demonstration, rolled back
BEGIN;
SELECT notam_id, action, replaces_notam_id, replaces_event_id, lifecycle_status
  FROM notam_event WHERE action IN ('R', 'C') ORDER BY event_id LIMIT 10;
SELECT * FROM resolve_notam_lifecycle();
SELECT lifecycle_status, count(*) FROM notam_event GROUP BY 1;
ROLLBACK;

-- Q16 Validity and flight-level range operators (S16)
SELECT notam_id, valid_during, fl_range,
       valid_during && tstzrange('2026-11-05 06:00+00', '2026-11-05 08:00+00', '[]') AS time_overlap,
       fl_range && int4range(0, 350, '[]') AS fl_overlap
  FROM notam_event ORDER BY event_id LIMIT 15;

-- Q17 Relevant-NOTAM retrieval for DEL-BOM (S17)  -- change ETD to a time covered by your data
WITH params AS (
    SELECT tstzrange('2026-11-05 06:00+00', '2026-11-05 08:00+00', '[]') AS win,
           int4range(0, 350, '[]') AS fl, 200 * 1852.0 AS corridor_m),
route AS (
    SELECT ST_MakeLine(s.location, d.location)::geography AS gc, s.fir_code AS src_fir, d.fir_code AS dst_fir
      FROM airport s, airport d WHERE s.icao_code = 'VIDP' AND d.icao_code = 'VABB'),
route_firs AS (
    SELECT f.icao_code FROM fir f, route r, params p
     WHERE f.boundary IS NOT NULL AND ST_DWithin(f.boundary::geography, r.gc, p.corridor_m)
    UNION SELECT src_fir FROM route UNION SELECT dst_fir FROM route)
SELECT n.notam_id, n.severity, n.category, n.icao_location, n.lower_fl, n.upper_fl, n.valid_during,
       CASE WHEN n.icao_location IN ('VIDP', 'VABB') THEN 'AERODROME'
            WHEN n.geom IS NOT NULL THEN 'CORRIDOR' ELSE 'FIR_WIDE' END AS match_reason,
       round((ST_Distance(n.geom::geography, r.gc) / 1852.0)::numeric, 1) AS distance_nm,
       left(n.e_text, 70) AS e_text
  FROM notam_event n CROSS JOIN route r CROSS JOIN params p
 WHERE n.lifecycle_status = 'ACTIVE' AND n.action IS DISTINCT FROM 'C'
   AND n.valid_during && p.win
   AND (n.icao_location IN ('VIDP', 'VABB')
        OR (n.fl_range && p.fl
            AND ((n.geom IS NOT NULL AND ST_DWithin(n.geom::geography, r.gc, p.corridor_m))
                 OR (n.geom IS NULL AND n.geom_source = 'FIR_WIDE'
                     AND n.fir_code IN (SELECT icao_code FROM route_firs)))))
 ORDER BY CASE n.severity WHEN 'BLOCKING' THEN 0 WHEN 'RESTRICTIVE' THEN 1 ELSE 2 END, distance_nm NULLS LAST;

-- Q18 Query plan + timing of the retrieval (S18): prefix Q17 with
--     EXPLAIN (ANALYZE, BUFFERS)
-- and read "Execution Time" at the bottom.

-- Q19 Normalisation check: one event per NOTAM identity, many raw observations (S19)
SELECT e.nof, e.notam_id, count(r.raw_id) AS observations
  FROM notam_event e JOIN raw_notam r ON r.nof = e.nof AND r.notam_id = e.notam_id
 GROUP BY 1, 2 HAVING count(r.raw_id) > 1 ORDER BY 3 DESC LIMIT 15;
