-- 001_init_schema.sql  -- shared v2 schema (methodology section 4)
--
-- Safe to run more than once: every object uses IF NOT EXISTS and the index
-- names are the ones PostgreSQL generated for the original unnamed
-- "CREATE INDEX ON ..." statements, so databases created from the first
-- version of this file are not given duplicate indexes.
--
-- pgRouting is optional (Person B may route with NetworkX); a missing
-- extension only raises a NOTICE instead of aborting the migration.

CREATE EXTENSION IF NOT EXISTS postgis;

DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS pgrouting;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pgrouting extension not available (%); continuing without it', SQLERRM;
END
$$;

CREATE TABLE IF NOT EXISTS data_source (source_id SERIAL PRIMARY KEY, name TEXT, access_type TEXT, active BOOLEAN);
CREATE TABLE IF NOT EXISTS ingestion_run (run_id BIGSERIAL PRIMARY KEY, source_id INT REFERENCES data_source,
  started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, records_fetched INT, status TEXT);
CREATE TABLE IF NOT EXISTS raw_notam (raw_id BIGSERIAL PRIMARY KEY, run_id BIGINT REFERENCES ingestion_run,
  notam_id TEXT, raw_text TEXT, fetched_at TIMESTAMPTZ, content_hash TEXT UNIQUE);

CREATE TABLE IF NOT EXISTS fir (icao_code TEXT PRIMARY KEY, name TEXT, boundary GEOMETRY(MultiPolygon,4326));
CREATE TABLE IF NOT EXISTS airport (icao_code TEXT PRIMARY KEY, iata_code TEXT, name TEXT, city TEXT,
  fir_code TEXT REFERENCES fir, location GEOMETRY(Point,4326));

CREATE TABLE IF NOT EXISTS notam_event (
  event_id BIGSERIAL PRIMARY KEY, raw_id BIGINT REFERENCES raw_notam,
  notam_id TEXT, action CHAR(1), replaces_event_id BIGINT REFERENCES notam_event,
  fir_code TEXT REFERENCES fir, icao_location TEXT,
  q_code TEXT, lower_fl INT, upper_fl INT,
  valid_during TSTZRANGE,
  geom GEOMETRY(Polygon,4326), radius_nm NUMERIC,
  category TEXT, severity TEXT, classifier_conf REAL, e_text TEXT);
CREATE INDEX IF NOT EXISTS notam_event_geom_idx ON notam_event USING GIST (geom);
CREATE INDEX IF NOT EXISTS notam_event_valid_during_idx ON notam_event USING GIST (valid_during);
CREATE INDEX IF NOT EXISTS notam_event_icao_location_fir_code_idx ON notam_event (icao_location, fir_code);

CREATE TABLE IF NOT EXISTS waypoint (waypoint_id SERIAL PRIMARY KEY, ident TEXT, location GEOMETRY(Point,4326));
CREATE TABLE IF NOT EXISTS airway (airway_id SERIAL PRIMARY KEY, designator TEXT);
CREATE TABLE IF NOT EXISTS airway_edge (edge_id SERIAL PRIMARY KEY, airway_id INT REFERENCES airway,
  from_waypoint_id INT REFERENCES waypoint, to_waypoint_id INT REFERENCES waypoint,
  dist_nm REAL, lower_fl INT, upper_fl INT, geom GEOMETRY(LineString,4326));

CREATE TABLE IF NOT EXISTS route_request (request_id BIGSERIAL PRIMARY KEY, origin_icao TEXT REFERENCES airport,
  dest_icao TEXT REFERENCES airport, etd_utc TIMESTAMPTZ, cruise_fl INT, cruise_tas_kt INT);
CREATE TABLE IF NOT EXISTS candidate_route (route_id BIGSERIAL PRIMARY KEY, request_id BIGINT REFERENCES route_request,
  total_dist_nm REAL, est_time_min REAL, is_feasible BOOLEAN, is_selected BOOLEAN,
  reject_reason TEXT, path GEOMETRY(LineString,4326));
CREATE TABLE IF NOT EXISTS route_conflict (conflict_id BIGSERIAL PRIMARY KEY, route_id BIGINT REFERENCES candidate_route,
  event_id BIGINT REFERENCES notam_event, conflict_type TEXT, explanation TEXT);

CREATE INDEX IF NOT EXISTS fir_boundary_idx ON fir USING GIST (boundary);
CREATE INDEX IF NOT EXISTS airport_location_idx ON airport USING GIST (location);
CREATE INDEX IF NOT EXISTS airway_edge_geom_idx ON airway_edge USING GIST (geom);
