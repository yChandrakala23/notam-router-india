# Person A demo script (about 4 minutes of the 10-minute demo)

Before the demo:

1. Data loaded (setup steps 5 and 7).
2. `uvicorn api.main:app` running.
3. pgAdmin open on database `notam`.
4. Pick an ETD inside the validity of your current data.

| Time | Show | Say |
|---|---|---|
| 0:00 | Terminal: `python -m ingestion.scheduler --once` (or `--offline`) | Adapters for AAI and autorouter share one interface. Each run is logged, and a re-run inserts 0 rows because of `content_hash`. |
| 0:40 | pgAdmin Q6 + Q7 | Run log and freshness per source. |
| 1:00 | pgAdmin Q10 | A real malformed AAI NOTAM (minute 90) was logged, not crashed. |
| 1:20 | pgAdmin Q12 + Geometry Viewer | Q-line → `ST_Buffer` circle in PostGIS; area ≈ πr². |
| 1:50 | pgAdmin Q11 | Merged classifier: RULES for Q-coded NOTAMs, ML/guard for AAI ones; low confidence → RESTRICTIVE. |
| 2:20 | Browser `/docs` → GET `/notams/relevant` (VIDP→VABB, FL350) | GeoJSON for Person B: severity, FL band, validity, geometry, match reason, `query_ms`. |
| 3:00 | Change `fl_hi` to 450, or move ETD past a NOTAM's end | Features appear or disappear: the time, FL and corridor rules at work. |
| 3:30 | `evaluation/results/*.md` | Parser accuracy, classifier macro-F1 (weak labels), retrieval recall, with its data-currency caveat. |

Always end with the disclaimer: "Decision support for research only; not for operational use."
