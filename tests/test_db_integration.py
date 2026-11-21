"""Live PostgreSQL/PostGIS integration tests (Person A).

Skipped unless NOTAM_DB_TESTS=1 and DATABASE_URL points at a migrated
database.  Everything runs inside one transaction that is ROLLED BACK, so no
data is left behind and existing rows are untouched.

    $env:NOTAM_DB_TESTS = "1"; python -m pytest tests/test_db_integration.py -v   (PowerShell)
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.db

if os.getenv("NOTAM_DB_TESTS") != "1":
    pytest.skip("set NOTAM_DB_TESTS=1 to run live database tests", allow_module_level=True)

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import text  # noqa: E402

from api.relevance import relevant_notams, relevant_notams_reference  # noqa: E402

FIXTURE = json.loads(Path("tests/fixtures/synthetic_notam_events.json").read_text())["events"]
ETD = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)
ETA = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    from api.db import get_engine

    connection = get_engine().connect()
    tx = connection.begin()
    try:
        yield connection
    finally:
        tx.rollback()
        connection.close()


def _insert_synthetic(conn):
    source_id = conn.execute(text(
        "INSERT INTO data_source (name, access_type, active) VALUES ('SYNTHETIC_TEST', 'manual', false) "
        "ON CONFLICT (name) DO UPDATE SET active = false RETURNING source_id")).scalar()
    run_id = conn.execute(text(
        "INSERT INTO ingestion_run (source_id, status) VALUES (:s, 'SUCCESS') RETURNING run_id"),
        {"s": source_id}).scalar()
    ids = {}
    for e in FIXTURE:
        raw_id = conn.execute(text(
            "INSERT INTO raw_notam (run_id, notam_id, nof, raw_text, raw_format, content_hash, parse_status) "
            "VALUES (:r, :n, 'SYNTHETIC', :t, 'icao_text', md5(:t) || md5(:n), 'PARSED') RETURNING raw_id"),
            {"r": run_id, "n": e["notam_id"], "t": "SYNTHETIC " + e["e_text"]}).scalar()
        event_id = conn.execute(text("""
            INSERT INTO notam_event (raw_id, notam_id, nof, action, lifecycle_status, fir_code,
                icao_location, q_code, lower_fl, upper_fl, valid_during, center, geom, radius_nm,
                geom_source, is_permanent, category, severity, classifier_conf, classifier_method, e_text)
            VALUES (:raw_id, :notam_id, 'SYNTHETIC', :action, :lifecycle_status, :fir_code,
                :icao_location, :q_code, :lower_fl, :upper_fl,
                tstzrange(CAST(:valid_from AS timestamptz), CAST(:valid_until AS timestamptz), '[]'),
                CASE WHEN :geom_source = 'QLINE_CIRCLE' THEN ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) END,
                CASE WHEN :geom_source = 'QLINE_CIRCLE'
                     THEN ST_Buffer(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_nm * 1852.0)::geometry
                     WHEN :geom_source = 'AERODROME_DEFAULT'
                     THEN (SELECT ST_Buffer(location::geography, :radius_nm * 1852.0)::geometry
                             FROM airport WHERE icao_code = :icao_location) END,
                :radius_nm, :geom_source, :is_permanent, :category, :severity, 1.0, 'RULES', :e_text)
            RETURNING event_id"""),
            {**e, "raw_id": raw_id, "lat": e["center_lat"], "lon": e["center_lon"]}).scalar()
        ids[event_id] = e["synthetic_case"]
    return ids


def test_postgis_available(conn):
    assert conn.execute(text("SELECT PostGIS_Version()")).scalar()


def test_methodology_buffer_is_a_valid_circle(conn):
    row = conn.execute(text("""
        SELECT ST_IsValid(g), ST_SRID(g), GeometryType(g),
               ST_Area(g::geography) / (pi() * (25 * 1852.0) ^ 2)
          FROM (SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(77.0, 28.5), 4326)::geography,
                                 25 * 1852.0)::geometry AS g) s""")).one()
    assert row[0] is True and row[1] == 4326 and row[2] == "POLYGON"
    assert 0.98 < row[3] <= 1.0


def test_sql_matches_reference_on_synthetic_events(conn):
    ids = _insert_synthetic(conn)
    result = relevant_notams("VIDP", "VABB", ETD, ETA, 0, 350, 200, connection=conn)
    got = {ids[f["id"]] for f in result["features"] if f["properties"]["nof"] == "SYNTHETIC"}
    reference = relevant_notams_reference(FIXTURE, "VIDP", "VABB", ETD, ETA, 0, 350, 200)
    reference_ids = {f["properties"]["event_id"] for f in reference["features"]}
    expected = {e["synthetic_case"] for e in FIXTURE if e["event_id"] in reference_ids}
    assert got == expected == {"corridor_blocking", "destination_closed_low_fl", "permanent",
                               "fir_wide_src", "corridor_edge_175nm"}


def test_lifecycle_function(conn):
    _insert_synthetic(conn)
    conn.execute(text("UPDATE notam_event SET action = 'R', replaces_notam_id = 'Z0003/26' "
                      "WHERE nof = 'SYNTHETIC' AND notam_id = 'Z0002/26'"))
    conn.execute(text("SELECT * FROM resolve_notam_lifecycle()"))
    status = conn.execute(text("SELECT lifecycle_status FROM notam_event "
                               "WHERE nof = 'SYNTHETIC' AND notam_id = 'Z0003/26'")).scalar()
    assert status == "REPLACED"


def test_constraints_reject_bad_rows(conn):
    _insert_synthetic(conn)
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        with conn.begin_nested():
            conn.execute(text("UPDATE notam_event SET severity = 'HIGH' WHERE nof = 'SYNTHETIC'"))
    # lower > upper fails in the generated fl_range column or the CHECK
    with pytest.raises(sqlalchemy.exc.DBAPIError):
        with conn.begin_nested():
            conn.execute(text("UPDATE notam_event SET lower_fl = 300, upper_fl = 100 WHERE nof = 'SYNTHETIC'"))


def test_plan_route_on_postgis_rejects_and_persists(conn):
    """End-to-end on PostGIS with SYNTHETIC events: retrieval -> conflict check -> persistence."""
    from routing.planner import plan_route

    _insert_synthetic(conn)
    # cruise FL200 passes through the synthetic BLOCKING circle (FL000-250) on the direct route
    result = plan_route("VIDP", "VABB", ETD, 200, connection=conn, persist=True)
    direct = next(r for r in result["rejected_routes"] + result["alternatives"] +
                  ([result["best_route"]] if result["best_route"] else []) if r["is_direct"])
    assert not direct["is_feasible"] and "Z0001/26" in direct["reject_reason"]
    assert result["best_route"] is None or not result["best_route"]["is_direct"]
    n_routes = conn.execute(text("SELECT count(*) FROM candidate_route WHERE request_id = :r"),
                            {"r": result["request_id"]}).scalar()
    n_hard = conn.execute(text("""SELECT count(*) FROM route_conflict c JOIN candidate_route r USING (route_id)
                                  WHERE r.request_id = :r AND c.conflict_type = 'HARD'"""),
                          {"r": result["request_id"]}).scalar()
    assert n_routes == result["candidates_evaluated"] and n_hard >= 1
