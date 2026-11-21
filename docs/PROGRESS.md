# Progress

## Audit and correction, 17 Nov 2026
- **Classification:**
  - shared taxonomy module;
  - annotation validator and audit;
  - training on weak + human labels, with source and label-type tracking, de-duplication, conflict flagging and independent per-field fitting;
  - leakage-safe evaluation: frozen grouped holdout, identical-split baseline-vs-improved comparison, per-repeat reporting, bootstrap CI;
  - explainable classifications (reason, keyword, uncertainty) stored in the DB (migration 004) and returned by the API;
  - keyword guard ignores deactivated/cancelled activity.
- **Routing (previously stubs):**
  - graph (DB airways or synthetic lattice);
  - Yen's K-shortest candidates;
  - space + vertical-profile + time conflict check;
  - selection with explanations;
  - POST /plan with persistence;
  - static_data loaders;
  - routing evaluation.
- **Fixed:**
  - en-route aerodrome closures no longer reject overflights;
  - AAI activity NOTAMs (e.g. SHAR launches under "CHENNAI VOMM") no longer get a misleading aerodrome circle;
  - weak-label CV no longer pools repeated predictions;
  - 16 duplicate weak examples removed;
  - small-training-set TF-IDF crash;
  - dev-CV crash with few templates.
- **Open:**
  - annotations are single-annotator; the audit flags questionable labels for review (none changed);
  - category improvement from human labels not established (severity improvement is supported);
  - curated ATS airway data not loaded;
  - web UI still a stub (Person B).

- **Done 21–22 Nov:** final annotated sheet (300 NOTAMs) integrated; near-duplicate-cluster hold-out; model retrained and DB events reclassified; routing evaluation 12/12.

*Updated 2026-11-22 (Person A). Person B: please add your own section.*

## Person A — Done
- Ingestion: common adapter interface (`ingestion/base.py`). AAI summary adapter, live and from saved snapshots. autorouter adapter, live and from saved snapshots. FAA and ICAO adapters, which are ready but untested because there are no keys.
- India filter (VI/VA/VE/VO, four FIRs). Idempotent raw store (`content_hash`). `ingestion_run` logging. Redacted errors.
- Scheduler (`--once`, `--loop --interval 15`, offline mode). AAI fetches throttled to once per 24 h.
- Q-line / ICAO NOTAM parser:
  - Q-line, A), B), C) with PERM and EST, D) kept as text, E), F)/G).
  - Malformed input is logged, never crashes.
  - Fixed a regex bug that rejected 72 of 143 real Q-lines.
- AAI summary parser: validity, schedule lines, page-furniture removal, aerodrome taken from section headings.
- Geometry: methodology `ST_Buffer(point::geography, r*1852)::geometry` in PostGIS, plus a pure-Python geodesic circle.
- Merged classifier: Q-code rules, TF-IDF + logistic-regression fallback, RESTRICTIVE default at low confidence, keyword guard.
- Database:
  - Migration 001 made idempotent.
  - 002: constraints, indexes, lifecycle function, freshness views.
  - 003: minimal FIR and airport rows.
  - Migration runner and checker (`python -m db.migrate`).
- NOTAMR/NOTAMC lifecycle in SQL (`resolve_notam_lifecycle()`).
- Retrieval: `api.relevance.relevant_notams` (PostGIS), plus a pure-Python reference and seed mode.
- `GET /notams/relevant` and `GET /notams/freshness`, with an optional Redis cache.
- Tests: 117 unit tests passing. DB integration tests written; they run only with `NOTAM_DB_TESTS=1`.
- Evaluation scripts:
  - parser (1,281 real records);
  - classifier (cross-validated, rules vs ML);
  - retrieval recall/precision vs autorouter;
  - SQL-vs-reference and timing check.
- Docs: DBMS report, ER diagram, report sections, Windows setup, pgAdmin screenshot plan, demo script, contract.

## Verified end to end (9 Nov 2026, PostgreSQL 16 + PostGIS 3.4 test server)
- Migrations, offline ingestion (idempotent), lifecycle, DB integration tests (5/5), live API, Redis cache, pgAdmin queries, all evaluation scripts.
- Fixed: SQLAlchemy 2.1 default-driver change (`api/db.py`); `ingestion/test_delhi.py` no longer downloads on import; CI no longer ignores test failures.

## Person A — Doing / to run on the local machine
- [ ] Remove the duplicate `POSTGRES_PASSWORD` line in `.env`, then `python -m db.migrate --check` and `python -m db.migrate`.
- [ ] `python -m ingestion.scheduler --once --offline`, then the DB integration tests.
- [ ] Download Oct/Nov 2026 AAI summaries and refresh autorouter (including VISR), then re-run `evaluation.relevance_recall`.
- [ ] `evaluation.retrieval_db_check`: record the SQL timings (target < 500 ms).
- [ ] 48 h unattended scheduler run.
- [ ] Hand-label `data/labelled/aai_label_sheet.csv` (300 rows), then re-run `classification.evaluate`.
- [ ] pgAdmin screenshots S1–S21 (`docs/person_a/pgadmin_screenshots.md`).

## Blocked
- FAA and ICAO live feeds: API keys not issued (`.env` empty).
- Integration with Person B: `routing/` and `static_data/` are still stubs in this repository snapshot (all git branches point at the scaffold commit). The contract (`docs/contract.md`) and seed mode let B integrate as soon as the code exists.
