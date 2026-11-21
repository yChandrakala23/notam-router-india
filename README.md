# NOTAM-Aware Flight Route Planning for Indian Airspace (v2)

Ingests NOTAMs, parses the Q-line into circle geometries, classifies severity, stores everything in PostGIS,
retrieves only trip-relevant NOTAMs, rejects conflicting routes and shows the shortest feasible route on a map.
*Decision support for research only; not for operational use.*

## Quick start
```bash
cp .env.example .env        # Windows: copy .env.example .env
docker compose up -d
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```

## Ownership
Person A: `ingestion/` `parsing/` `classification/` `api/relevance.py` `db/`
Person B: `static_data/` `routing/` `api/` `web/`
Shared: `tests/` `evaluation/` `docs/`

## Person A: data and NOTAM intelligence

Step-by-step Windows setup (local PostgreSQL 14 + PostGIS on port 5433): `docs/person_a/setup_windows.md`.

```bash
python -m db.migrate --check            # read-only environment check (never prints secrets)
python -m db.migrate                    # apply db/migrations/*.sql (idempotent)
python -m classification.train          # train E-text fallback model (needs data/autorouter snapshot)
python -m ingestion.scheduler --once --offline   # load saved AAI + autorouter snapshots
python -m ingestion.scheduler --loop --interval 15   # live polling
uvicorn api.main:app --reload           # GET /notams/relevant, GET /notams/freshness
python -m pytest -q                     # unit tests (DB tests: set NOTAM_DB_TESTS=1)
python -m evaluation.parser_eval        # + classification.evaluate, evaluation.relevance_recall,
                                        #   evaluation.retrieval_db_check
```

| Topic | Location |
|---|---|
| Interface for Person B | `docs/contract.md` |
| DBMS report | `docs/person_a/dbms_report.md` |
| ER diagram | `docs/person_a/er_diagram.png` |
| Report sections | `docs/person_a/report_sections.md` |
| pgAdmin queries | `db/sql/pgadmin_queries.sql` |
| Screenshot plan | `docs/person_a/pgadmin_screenshots.md` |
| Demo script | `docs/person_a/demo.md` |

Data handling:

- `data/autorouter/` is commercial and git-ignored. Never commit it, or the trained model derived from it.
- `.env` is never committed.
- Synthetic NOTAMs exist only in `tests/` and are labelled SYNTHETIC.

## Documentation map (updated 17 Nov 2026)

| Topic | File |
|---|---|
| Run everything on Windows | `docs/RUNNING.md` |
| Classification: taxonomy, annotation, training, leakage-safe evaluation | `docs/person_a/classification_methodology.md` |
| Routing: graph, candidates, conflict check, selection, POST /plan | `docs/routing_methodology.md` |
| Generated results | `evaluation/results/*.md` |

Research decision-support prototype; not certified and not for operational use.
