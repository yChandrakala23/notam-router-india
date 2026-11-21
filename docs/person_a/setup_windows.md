# Person A setup on Windows (PowerShell, local PostgreSQL 14 + PostGIS on port 5433)

Run every command in **PowerShell**, from the repository folder (the folder that contains `README.md`). Do one step at a time and check its output before moving on. Nothing here deletes or resets a database.

## Step 0 — Fix `.env` (once)

Your `.env` currently contains **two** `POSTGRES_PASSWORD=` lines with different values, and the second one does not match the password inside `DATABASE_URL`. This is the likely cause of the earlier password confusion.

1. Open `.env` in Notepad: `notepad .env`
2. Delete the **second** `POSTGRES_PASSWORD=` line (the last line of the file). Keep the one that matches the password in `DATABASE_URL`.
3. Save the file. Do not paste the password anywhere else.

Check without printing secrets. This prints only names and lengths:

```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^([^=]+)=(.*)$') { "{0}  length={1}" -f $matches[1], $matches[2].Length } }
```

Each name should now appear exactly once.

## Step 1 — Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pydantic sqlalchemy psycopg2-binary httpx python-dotenv pypdf scikit-learn joblib pandas numpy pytest redis
```

The full `requirements.txt` also lists geopandas and prefect. Person A's code does not need them, and they are heavy on Python 3.14. Install them only if Person B needs them.

If activation is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Step 2 — Unit tests (no database needed)

```powershell
python -m pytest -q
```

Expected: all tests pass. One file is skipped (`test_db_integration`), which is normal at this point.

## Step 3 — Read-only database check

```powershell
python -m db.migrate --check
```

Send me the output. It shows the target (user@host:5433/notam), the PostgreSQL version, whether `postgis` is installed, and which tables already exist. It never prints the password.

- If it says `database "notam" does not exist`, create it in pgAdmin: right-click **Databases → Create → Database…**, name `notam`, owner = the user in `DATABASE_URL`.
- If `postgis` shows `installed=-`, run `CREATE EXTENSION postgis;` in the pgAdmin Query Tool on database `notam`. Migration 001 also tries this, but it needs a role with the right privileges.

## Step 4 — Apply migrations

```powershell
python -m db.migrate
python -m db.migrate --status
```

All three files should be reported as applied. Running the command again is safe.

## Step 5 — First load from the saved snapshots (no network)

```powershell
python -m classification.train
python -m ingestion.scheduler --once --offline
```

The first command trains the text model from your local autorouter snapshot. The second stores the AAI and autorouter snapshots and builds `notam_event`. Note the printed counts (fetched / inserted / duplicates, then parsed / failed / events_written).

Run the second command again: it should report `inserted=0` and `duplicates` equal to the number fetched. That demonstrates idempotency.

## Step 6 — Database integration tests

```powershell
$env:NOTAM_DB_TESTS = "1"
python -m pytest tests/test_db_integration.py -v
Remove-Item Env:NOTAM_DB_TESTS
```

These run inside a transaction that is rolled back, so nothing is left behind.

## Step 7 — Live data (makes the evaluation meaningful)

The repository's AAI summaries for Delhi, Mumbai and Kolkata stop at April–July 2026. Download the current ones:

```powershell
python -m ingestion.aai --months 2026-10 2026-11 --save-jsonl
python -m ingestion.autorouter
python -m ingestion.scheduler --once --offline
```

The second command refreshes the private autorouter snapshot, and now includes VISR for DEL–SXR. The third loads the new files.

For unattended polling (plan: 48 h):

```powershell
python -m ingestion.scheduler --loop --interval 15
```

Alternatively, use **Windows Task Scheduler**: create a task that runs every 15 minutes with

- Program: `<repo>\.venv\Scripts\python.exe`
- Arguments: `-m ingestion.scheduler --once`
- Start in: `<repo>`

Logs are written to `logs\ingestion.log`.

## Step 8 — API

```powershell
uvicorn api.main:app --reload
```

Then open http://127.0.0.1:8000/docs and try **GET /notams/relevant** with `src=VIDP`, `dst=VABB`, `etd=` a current UTC time such as `2026-11-05T06:00:00Z`, and `fl_hi=350`.

## Step 9 — Evaluation

```powershell
python -m evaluation.parser_eval
python -m classification.evaluate
python -m evaluation.relevance_recall --etd 2026-11-04T12:00:00Z --db
python -m evaluation.retrieval_db_check --etd 2026-11-04T12:00:00Z
```

Results are written to `evaluation\results\*.md` and `*.json`.

For `relevance_recall`, use an ETD close to when you last ran `python -m ingestion.autorouter`. Its reference set is that snapshot.
