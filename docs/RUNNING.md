# Running the project on Windows (PowerShell)

Run everything from the repository folder, the one that contains `README.md`, in PowerShell. Database: local PostgreSQL 14 + PostGIS on port 5433 (see `docs/person_a/setup_windows.md` for first-time database setup and the `.env` check).

## 1. Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pydantic sqlalchemy psycopg2-binary httpx python-dotenv pypdf scikit-learn joblib pandas numpy networkx pytest redis
```

## 2. Database

```powershell
python -m db.migrate --check          # read-only: versions, extensions, tables (never prints secrets)
python -m db.migrate                  # applies 001-004 (idempotent)
```

## 3. Load data

```powershell
python -m classification.train --labels weak        # baseline model (needed before processing)
python -m ingestion.scheduler --once --offline      # load saved AAI + autorouter snapshots
```

To refresh and reclassify everything after retraining:

```powershell
python -m ingestion.scheduler --process-only --reprocess-failed
```

## 4. Annotations, training, evaluation

```powershell
python -m classification.annotations                # audit data\labelled\aai_label_sheet.csv
python -m classification.train --labels weak        # BASELINE model
python -m classification.evaluate                   # weak-label CV + leakage-safe baseline vs improved
python -m classification.train                      # IMPROVED model (weak + human, hold-out excluded)
python -m classification.train --use-holdout        # final model on all labels (hold-out numbers no longer apply)
```

Reports are written to `evaluation\results\annotation_audit.md`, `classifier_eval.md`. The frozen holdout is saved to `data\labelled\aai_holdout_split.json`; keep it unchanged so results stay comparable (`--resplit` redraws it).

## 5. Other evaluations

```powershell
python -m evaluation.parser_eval
python -m evaluation.relevance_recall --etd 2026-10-16T22:00:00Z --db
python -m evaluation.retrieval_db_check --etd 2026-10-16T22:00:00Z
python -m evaluation.routing_eval --etd 2026-10-16T22:00:00Z
python -m evaluation.routing_eval --synthetic-only      # no database needed
```

## 6. Tests

```powershell
python -m pytest -q                                   # unit tests, no database needed
$env:NOTAM_DB_TESTS = "1"; python -m pytest tests/test_db_integration.py -v; Remove-Item Env:NOTAM_DB_TESTS
```

## 7. Start the application

```powershell
uvicorn api.main:app --reload
```

Open http://127.0.0.1:8000/docs. Try:

- **GET /notams/relevant**: `src=VIDP`, `dst=VABB`, `etd=2026-10-16T22:00:00Z`, `fl_hi=350`
- **POST /plan**: `{"src":"VIDP","dst":"VOBL","etd":"2026-10-16T22:00:00Z","fl":350}`

Choose an ETD that your loaded NOTAM data covers.

## Data handling

- **Commercial data.** `data/autorouter/` is commercial autorouter data; never commit or share it. The same goes for the trained model (`classification/models/*.joblib`), which is derived from it.
- **Credentials.** `.env` holds credentials and is git-ignored.

Decision support for research only; not for operational use.
