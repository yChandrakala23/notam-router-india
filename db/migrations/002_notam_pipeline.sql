-- 002_notam_pipeline.sql  -- Person A: ingestion, raw store, structured NOTAM events
--
-- Extends (does not recreate) the tables from 001 so that existing data and
-- Person B's tables are untouched.  Re-runnable: ADD COLUMN IF NOT EXISTS,
-- CREATE INDEX IF NOT EXISTS, constraints added only when missing.
--
-- All timestamps are TIMESTAMPTZ and stored in UTC.

-- -------------------------------------------------------------------------
-- helper: add a constraint only if it does not exist yet
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION pg_temp.add_constraint(tbl regclass, cname text, ddl text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = cname AND conrelid = tbl) THEN
    EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', tbl, cname, ddl);
  END IF;
END
$$;

-- -------------------------------------------------------------------------
-- data_source
-- -------------------------------------------------------------------------
ALTER TABLE data_source
  ADD COLUMN IF NOT EXISTS base_url          TEXT,
  ADD COLUMN IF NOT EXISTS poll_interval_min INT  NOT NULL DEFAULT 15,
  ADD COLUMN IF NOT EXISTS created_at        TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE data_source ALTER COLUMN name SET NOT NULL;
ALTER TABLE data_source ALTER COLUMN active SET DEFAULT true;
CREATE UNIQUE INDEX IF NOT EXISTS data_source_name_uq ON data_source (name);
DO $do$ BEGIN PERFORM pg_temp.add_constraint('data_source', 'data_source_access_type_ck',
  $c$CHECK (access_type IN ('api', 'pdf', 'file', 'manual'))$c$); END $do$;

-- -------------------------------------------------------------------------
-- ingestion_run  (one row per adapter execution)
-- -------------------------------------------------------------------------
ALTER TABLE ingestion_run
  ADD COLUMN IF NOT EXISTS records_inserted  INT,
  ADD COLUMN IF NOT EXISTS records_duplicate INT,
  ADD COLUMN IF NOT EXISTS records_failed    INT,
  ADD COLUMN IF NOT EXISTS error_message     TEXT,
  ADD COLUMN IF NOT EXISTS trigger           TEXT;
ALTER TABLE ingestion_run ALTER COLUMN started_at SET DEFAULT now();
UPDATE ingestion_run SET started_at = now() WHERE started_at IS NULL;
ALTER TABLE ingestion_run ALTER COLUMN started_at SET NOT NULL;
ALTER TABLE ingestion_run ALTER COLUMN source_id SET NOT NULL;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('ingestion_run', 'ingestion_run_status_ck',
  $c$CHECK (status IN ('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED', 'SKIPPED'))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('ingestion_run', 'ingestion_run_times_ck',
  $c$CHECK (finished_at IS NULL OR finished_at >= started_at)$c$); END $do$;
CREATE INDEX IF NOT EXISTS ingestion_run_source_started_idx
  ON ingestion_run (source_id, started_at DESC);

-- -------------------------------------------------------------------------
-- raw_notam  (append-only observations, raw text unchanged)
-- -------------------------------------------------------------------------
ALTER TABLE raw_notam
  ADD COLUMN IF NOT EXISTS nof           TEXT,
  ADD COLUMN IF NOT EXISTS raw_format    TEXT NOT NULL DEFAULT 'icao_text',
  ADD COLUMN IF NOT EXISTS source_url    TEXT,
  ADD COLUMN IF NOT EXISTS location_hint TEXT,
  ADD COLUMN IF NOT EXISTS parse_status  TEXT NOT NULL DEFAULT 'PENDING',
  ADD COLUMN IF NOT EXISTS parse_error   TEXT,
  ADD COLUMN IF NOT EXISTS parsed_at     TIMESTAMPTZ;
ALTER TABLE raw_notam ALTER COLUMN raw_text SET NOT NULL;
ALTER TABLE raw_notam ALTER COLUMN content_hash SET NOT NULL;
ALTER TABLE raw_notam ALTER COLUMN fetched_at SET DEFAULT now();
ALTER TABLE raw_notam ALTER COLUMN fetched_at SET NOT NULL;
ALTER TABLE raw_notam ALTER COLUMN run_id SET NOT NULL;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('raw_notam', 'raw_notam_format_ck',
  $c$CHECK (raw_format IN ('icao_text', 'aai_summary', 'autorouter_json'))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('raw_notam', 'raw_notam_parse_status_ck',
  $c$CHECK (parse_status IN ('PENDING', 'PARSED', 'FAILED', 'SKIPPED'))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('raw_notam', 'raw_notam_hash_ck',
  $c$CHECK (content_hash ~ '^[0-9a-f]{64}$')$c$); END $do$;
CREATE INDEX IF NOT EXISTS raw_notam_notam_id_idx ON raw_notam (nof, notam_id);
CREATE INDEX IF NOT EXISTS raw_notam_pending_idx ON raw_notam (raw_id) WHERE parse_status = 'PENDING';
CREATE INDEX IF NOT EXISTS raw_notam_run_idx ON raw_notam (run_id);

-- -------------------------------------------------------------------------
-- notam_event  (one row per NOTAM identity = issuing office + NOTAM id)
-- -------------------------------------------------------------------------
ALTER TABLE notam_event
  ADD COLUMN IF NOT EXISTS nof               TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS series            CHAR(1),
  ADD COLUMN IF NOT EXISTS notam_number      INT,
  ADD COLUMN IF NOT EXISTS notam_year        INT,
  ADD COLUMN IF NOT EXISTS replaces_notam_id TEXT,
  ADD COLUMN IF NOT EXISTS lifecycle_status  TEXT NOT NULL DEFAULT 'ACTIVE',
  ADD COLUMN IF NOT EXISTS traffic           TEXT,
  ADD COLUMN IF NOT EXISTS purpose           TEXT,
  ADD COLUMN IF NOT EXISTS scope             TEXT,
  ADD COLUMN IF NOT EXISTS center            GEOMETRY(Point, 4326),
  ADD COLUMN IF NOT EXISTS geom_source       TEXT NOT NULL DEFAULT 'NONE',
  ADD COLUMN IF NOT EXISTS is_permanent      BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS end_estimated     BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS schedule_text     TEXT,
  ADD COLUMN IF NOT EXISTS classifier_method TEXT,
  ADD COLUMN IF NOT EXISTS source_rank       SMALLINT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at        TIMESTAMPTZ NOT NULL DEFAULT now();

-- Flight-level range as a first-class, indexable value.  NULL limits mean
-- "unknown" and become unbounded range ends (conservative).
ALTER TABLE notam_event
  ADD COLUMN IF NOT EXISTS fl_range INT4RANGE
  GENERATED ALWAYS AS (int4range(lower_fl, upper_fl, '[]')) STORED;

ALTER TABLE notam_event ALTER COLUMN notam_id SET NOT NULL;
ALTER TABLE notam_event ALTER COLUMN action SET NOT NULL;
ALTER TABLE notam_event ALTER COLUMN valid_during SET NOT NULL;
ALTER TABLE notam_event ALTER COLUMN raw_id SET NOT NULL;

DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_identity_uq',
  $c$UNIQUE (nof, notam_id)$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_id_format_ck',
  $c$CHECK (notam_id ~ '^[A-Z][0-9]{4}/[0-9]{2}$')$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_action_ck',
  $c$CHECK (action IN ('N', 'R', 'C'))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_lifecycle_ck',
  $c$CHECK (lifecycle_status IN ('ACTIVE', 'REPLACED', 'CANCELLED'))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_severity_ck',
  $c$CHECK (severity IN ('BLOCKING', 'RESTRICTIVE', 'ADVISORY'))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_category_ck',
  $c$CHECK (category IN ('AIRSPACE_RESTRICTION', 'NAV_WARNING', 'AERODROME',
                         'RUNWAY', 'NAVAID_COMMS', 'OBSTACLE', 'PROCEDURE', 'OTHER'))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_fl_ck',
  $c$CHECK ((lower_fl IS NULL OR lower_fl BETWEEN 0 AND 999)
        AND (upper_fl IS NULL OR upper_fl BETWEEN 0 AND 999)
        AND (lower_fl IS NULL OR upper_fl IS NULL OR lower_fl <= upper_fl))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_radius_ck',
  $c$CHECK (radius_nm IS NULL OR radius_nm BETWEEN 0 AND 999)$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_conf_ck',
  $c$CHECK (classifier_conf IS NULL OR classifier_conf BETWEEN 0 AND 1)$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_validity_ck',
  $c$CHECK (NOT isempty(valid_during) AND NOT lower_inf(valid_during))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_geom_source_ck',
  $c$CHECK (geom_source IN ('QLINE_CIRCLE', 'AERODROME_DEFAULT', 'FIR_WIDE', 'NONE'))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_geom_valid_ck',
  $c$CHECK (geom IS NULL OR ST_IsValid(geom))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_method_ck',
  $c$CHECK (classifier_method IS NULL OR classifier_method IN
            ('RULES', 'RULES+ML', 'ML', 'ML_LOW_CONF_DEFAULT', 'KEYWORD_GUARD', 'DEFAULT'))$c$); END $do$;
DO $do$ BEGIN PERFORM pg_temp.add_constraint('notam_event', 'notam_event_no_self_replace_ck',
  $c$CHECK (replaces_event_id IS NULL OR replaces_event_id <> event_id)$c$); END $do$;

-- Spatial index usable by ST_DWithin(geom::geography, ...) in retrieval.
CREATE INDEX IF NOT EXISTS notam_event_geog_idx ON notam_event USING GIST ((geom::geography));
CREATE INDEX IF NOT EXISTS notam_event_fl_range_idx ON notam_event USING GIST (fl_range);
CREATE INDEX IF NOT EXISTS notam_event_fir_idx ON notam_event (fir_code);
CREATE INDEX IF NOT EXISTS notam_event_replaces_idx ON notam_event (replaces_event_id);
CREATE INDEX IF NOT EXISTS notam_event_raw_idx ON notam_event (raw_id);
-- Partial index on the rows retrieval can ever return.
CREATE INDEX IF NOT EXISTS notam_event_active_validity_idx ON notam_event
  USING GIST (valid_during) WHERE lifecycle_status = 'ACTIVE' AND action <> 'C';

-- keep updated_at honest
CREATE OR REPLACE FUNCTION notam_event_touch() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$;
DROP TRIGGER IF EXISTS notam_event_touch_trg ON notam_event;
CREATE TRIGGER notam_event_touch_trg BEFORE UPDATE ON notam_event
  FOR EACH ROW EXECUTE FUNCTION notam_event_touch();

-- -------------------------------------------------------------------------
-- NOTAMR / NOTAMC lifecycle resolution
--   * link R/C events to the event they reference (same issuing office)
--   * mark referenced events REPLACED / CANCELLED (CANCELLED wins)
-- Safe to call repeatedly; returns the number of rows changed.
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION resolve_notam_lifecycle()
RETURNS TABLE (linked INT, replaced INT, cancelled INT) LANGUAGE plpgsql AS $$
DECLARE
  n_linked INT; n_replaced INT; n_cancelled INT;
BEGIN
  UPDATE notam_event r
     SET replaces_event_id = o.event_id
    FROM notam_event o
   WHERE r.action IN ('R', 'C')
     AND r.replaces_event_id IS NULL
     AND r.replaces_notam_id IS NOT NULL
     AND o.nof = r.nof
     AND o.notam_id = r.replaces_notam_id
     AND o.event_id <> r.event_id;
  GET DIAGNOSTICS n_linked = ROW_COUNT;

  UPDATE notam_event o
     SET lifecycle_status = 'CANCELLED'
   WHERE o.lifecycle_status <> 'CANCELLED'
     AND EXISTS (SELECT 1 FROM notam_event c
                  WHERE c.replaces_event_id = o.event_id AND c.action = 'C');
  GET DIAGNOSTICS n_cancelled = ROW_COUNT;

  UPDATE notam_event o
     SET lifecycle_status = 'REPLACED'
   WHERE o.lifecycle_status = 'ACTIVE'
     AND EXISTS (SELECT 1 FROM notam_event r
                  WHERE r.replaces_event_id = o.event_id AND r.action = 'R');
  GET DIAGNOSTICS n_replaced = ROW_COUNT;

  RETURN QUERY SELECT n_linked, n_replaced, n_cancelled;
END
$$;

-- -------------------------------------------------------------------------
-- Views for monitoring / pgAdmin
-- -------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_source_freshness AS
SELECT s.source_id,
       s.name,
       s.access_type,
       s.active,
       s.poll_interval_min,
       last_ok.finished_at                      AS last_success_at,
       last_any.started_at                      AS last_attempt_at,
       last_any.status                          AS last_status,
       last_ok.records_fetched                  AS last_records_fetched,
       ROUND(EXTRACT(EPOCH FROM (now() - last_ok.finished_at)) / 60.0, 1) AS minutes_since_success,
       (last_ok.finished_at IS NULL
        OR now() - last_ok.finished_at > make_interval(mins => 2 * s.poll_interval_min)) AS is_stale
  FROM data_source s
  LEFT JOIN LATERAL (
        SELECT r.finished_at, r.records_fetched
          FROM ingestion_run r
         WHERE r.source_id = s.source_id AND r.status IN ('SUCCESS', 'PARTIAL')
         ORDER BY r.finished_at DESC NULLS LAST LIMIT 1) last_ok ON true
  LEFT JOIN LATERAL (
        SELECT r.started_at, r.status
          FROM ingestion_run r
         WHERE r.source_id = s.source_id
         ORDER BY r.started_at DESC LIMIT 1) last_any ON true;

CREATE OR REPLACE VIEW v_active_notam AS
SELECT e.*
  FROM notam_event e
 WHERE e.lifecycle_status = 'ACTIVE' AND e.action <> 'C';
