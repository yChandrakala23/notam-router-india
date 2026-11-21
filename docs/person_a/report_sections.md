# Person A report sections: Data, Ingestion, Q-line Parsing, Classifier, Evaluation

*All numbers below were produced by the scripts named next to them, run on the repository snapshot (AAI summaries as saved in `data/raw/`, autorouter snapshot of 16 Oct 2026). Re-run them after refreshing the data and update the tables. The database chapter is `dbms_report.md`. Decision support for research only; not for operational use.*

---

## 1. Data sources

| Source | Access | Status in this project | Volume (snapshot) |
|---|---|---|---|
| **AAI AIM India monthly NOTAM summaries** (public PDFs) | `ingestion/aai.py`: download PDF, extract text (pypdf), split at NOTAM ids | **Primary real source used.** Regions Delhi (VIDP), Mumbai (VABB), Chennai (VOMM), Kolkata (VECC) | 1,647 PDF blocks → **1,135 unique raw records** → **1,128 unique NOTAMs** |
| **autorouter.aero** NOTAM API | OAuth2 client credentials; `ingestion/autorouter.py` | Working (account in `.env`). Used as a Q-line source, for weak labels, and as the retrieval reference. **Commercial: kept local, git-ignored** | 143 NOTAMs for VIDP, VABB, VOBL, VOMM, VECC, VOHY |
| FAA NOTAM API | `ingestion/faa.py` | Implemented, **not run**: `FAA_API_CLIENT_ID/SECRET` empty | 0 |
| ICAO API Data Service | `ingestion/icao.py` | Implemented, **not run**: `ICAO_API_KEY` empty | 0 |
| ISRO launch NOTAMs (ICAO text) | `tests/fixtures/qline/` | 3 real historical NOTAMs used as parser fixtures | 3 |
| Synthetic NOTAMs | `tests/fixtures/synthetic_notam_events.json`, test files | **Labelled SYNTHETIC**; used only in tests | 12 events |

**500+ raw NOTAM target.** Met with real data: 1,135 unique raw AAI records + 143 autorouter = **1,278 unique raw records**, giving 1,245 distinct NOTAM events after merging the 25 NOTAMs present in both sources. No synthetic record is counted.

**Limitations of the data:**

- **No Q-line in AAI summaries.** There is no Q-code, FL band or centre/radius. These come from the classifier (category/severity) and from an aerodrome-centred default circle.
- **Monthly snapshots.** A summary lists NOTAMs in force on the 1st of the month. Delhi, Mumbai and Kolkata are only available up to April–July 2026; Chennai up to October 2026.
- **Small, airport-scoped autorouter snapshot.** 143 records, Item A only. VISR (Srinagar) was not fetched.

## 2. Ingestion

- **Common interface** (`ingestion/base.py`). Each adapter implements `SourceAdapter.fetch() → list[RawNotam]` and also defines:
  - `name` and `access_type`;
  - `is_configured()`;
  - `min_interval_min`, the throttle (AAI: 24 h).
- **India filter.** Locations matching `^V[AEIO][A-Z]{2}$` and FIRs VIDF, VABF, VECF, VOMF. This keeps out Nepal (VN), Sri Lanka (VC) and Pakistan (OP).
- **Raw text is stored unchanged.** `raw_format` is one of `icao_text`, `aai_summary` or `autorouter_json`.
- **Idempotent ingestion.** `raw_notam.content_hash` is UNIQUE and inserts use `ON CONFLICT DO NOTHING`. For AAI blocks the hash is computed after removing PDF page furniture (running titles, "Page n of m"), so the same NOTAM reprinted in the next monthly summary collapses. 1,647 → 1,135 **[parser_eval]**.
- **Run logging.** Every adapter execution creates an `ingestion_run` row with counts (fetched / inserted / duplicate / failed) and a status (SUCCESS, PARTIAL, FAILED, SKIPPED). Unconfigured FAA/ICAO runs are recorded as SKIPPED. Error messages pass through `redact()` (API keys, passwords, DSN passwords) before they are stored or logged.
- **Lifecycle.** NOTAMR/NOTAMC are resolved in SQL after each batch (`resolve_notam_lifecycle()`; DBMS §16).
- **Scheduling.** `python -m ingestion.scheduler --loop --interval 15`, or Windows Task Scheduler with `--once`. **The 48-hour unattended run has not been carried out yet [to fill].**
- **Robustness.** A failing source never stops the others. A malformed NOTAM is marked FAILED with its reason and does not crash the run (e.g. the real AAI record `A1046/26 … /2606021390EST`, minute = 90).

## 3. Q-line parsing and geometry (`parsing/qline.py`)

**Parsed fields:**

- **NOTAM header:** id (series, number, year), action N/R/C, referenced id.
- **Q-line:** FIR, Q-code (subject + condition), traffic, purpose, scope, lower/upper FL, centre (DDMM[NS]DDDMM[EW]), radius (NM).
- **Items:**
  - A) locations (stopping at "PART n OF m");
  - B) / C) UTC `YYMMDDHHMM`, with `PERM` = open-ended and `EST` = stated end used plus a flag;
  - D) kept as text (not interpreted, per methodology v2);
  - E) text;
  - F) / G) limits.

**Validation.** Minutes ≥ 60, latitude > 90, longitude > 180, lower FL > upper FL, an impossible date (month 13, hour 24, minute 90) and C) before B) are all reported as errors, never raised as exceptions.

**Robustness fix.** The original regex required 2-letter traffic and 1-letter scope. It rejected **72 of the 143** real autorouter Q-lines (traffic `I`, scope `AE`, padded fields). The new parser accepts all 143.

**Geometry:**

- **In the DB:** `ST_Buffer(ST_SetSRID(ST_MakePoint(lon,lat),4326)::geography, r·1852)::geometry` — the methodology formula, stored as `geometry(Polygon,4326)`.
- **Special cases:**
  - Radius 000 → 1 NM minimum.
  - Radius 999 or no coordinates on FIR scope → `FIR_WIDE` (no circle).
  - AAI records → 5 NM circle around the aerodrome reference point when the aerodrome is in `airport` (`AERODROME_DEFAULT`).
- **In Python** (`circle_polygon`): a 64-vertex geodesic circle, used for seed mode and tests.

**Other formats:**

- **AAI summaries** (`parsing/aai_summary.py`): header + validity, schedule lines, furniture removal, and aerodrome assignment from section headings. A heading lands at the *end of the previous block*, so it is tracked statefully in document order.
- **autorouter JSON** (`parsing/autorouter_record.py`): rendered to ICAO text and parsed by the same parser (single code path).

## 4. Merged classifier (`classification/`)

**Stage 1 — Q-code rules** (`rules.py`). Subject and condition meanings were checked against the FAA's published ICAO NOTAM code tables (JO 7930.2, ICAO Q-codes appendix).

| Rule (examples) | Category | Severity |
|---|---|---|
| R** (RA, RD, RP, RR, RT, RM, RO), active | AIRSPACE_RESTRICTION | BLOCKING |
| WM (rocket/missile/gun firing), WD, WW, WR | NAV_WARNING | BLOCKING |
| Other W** (UAS, parachuting, balloons, exercises…) | NAV_WARNING | RESTRICTIVE |
| FALC (aerodrome closed) | AERODROME | BLOCKING (at source/destination) |
| FA limited (LT, LN, AU, AH…) | AERODROME | RESTRICTIVE |
| MR/MT/MD/MS/MW… LC (runway closed) | RUNWAY | RESTRICTIVE |
| N**/I**/G**/C** unserviceable (AS, AU, AW, LC, CT…) | NAVAID_COMMS | RESTRICTIVE |
| AR (ATS route) closed / not available | PROCEDURE | RESTRICTIVE |
| Conditions CD, CN, AK, AX, HV, CC, AO, HQ (deactivated / normal) | — | ADVISORY |
| Obstacles, lighting, taxiway/apron, procedures, other | … | ADVISORY |
| QXXXX, QKKKK, condition XX | ambiguous | → stage 2 |

**Stage 2 — ML fallback** (`ml.py`).

- **Model:** TF-IDF (word 1–2-grams + char 3–5-grams) and logistic regression with balanced class weights, run on the E-text. Two models: category and severity.
- **When it is used:** only when the Q-code is missing (all AAI records) or ambiguous.
- **Low confidence:** a severity probability below 0.55 gives **RESTRICTIVE**.
- **Keyword guard:** can only *raise* severity. "ROCKET LAUNCH", "NO FLT IS PERMITTED", "AD CLSD / AIRFIELD CLOSURE" → BLOCKING; UAS, laser, parachuting, balloons, GNSS interference → RESTRICTIVE. It exists because the weak-label set contains only 3 BLOCKING examples, so the model alone cannot learn that class.

**Training data** (`dataset.py`, `train.py`):

- Total: **130 weak-labelled examples** = 112 autorouter records with an unambiguous Q-code + 3 ISRO fixtures + 15 AAI E-texts whose identity matches an autorouter record.
- Category counts: PROCEDURE 47, AERODROME 41, RUNWAY 19, OBSTACLE 15, NAVAID_COMMS 5, NAV_WARNING 3.
- Severity counts: ADVISORY 109, RESTRICTIVE 18, BLOCKING 3.

**Human labels.** `data/labelled/aai_label_sheet.csv` holds **300 hand-labelled AAI NOTAMs** (final sheet, 21 Nov 2026; severity RESTRICTIVE 176, ADVISORY 107, BLOCKING 17). 101 are a frozen hold-out never used for training; the deployed model is trained on 186 development labels plus 102 weak labels after leakage removal. Results: section 5.2 and `classification_methodology.md` section 6.3.

**Classification of the 1,245 stored events** (snapshot after retraining on the human labels, 22 Nov 2026):

| By method | Count |
|---|---|
| ML | 949 |
| RULES | 112 |
| ML_LOW_CONF_DEFAULT | 110 |
| KEYWORD_GUARD | 39 |
| RULES+ML | 28 |
| DEFAULT | 7 |

| By severity | Count |
|---|---|
| RESTRICTIVE | 728 |
| ADVISORY | 464 |
| BLOCKING | 53 |

The shift from ADVISORY (971 before) towards RESTRICTIVE reflects the annotators' labelling of AAI NOTAMs; it is not a measured accuracy on these 1,245 events.

## 5. Evaluation (data side)

### 5.1 Parser (`python -m evaluation.parser_eval` → `evaluation/results/parser_eval.md`)

| Test set | Reference | Records | Field accuracy |
|---|---|---|---|
| A. AAI summaries, parse success | — | 1,135 unique | 1,134 parsed (99.91%); 1 failure = genuinely malformed source record |
| A. AAI vs autorouter (independent provider) | autorouter fields for the same NOTAM | 25 NOTAMs × 6 fields | **150/150 (100%)** (B, C, PERM, EST, id, aerodrome) |
| B. autorouter Q-line round trip | source JSON | 143 × 15 fields | **2,145/2,145 (100%)** |
| C. ISRO ICAO-text fixtures | hand-checked values | 3 × 10 fields | 30/30 (100%) |
| Geometry (circles from 143 real Q-lines) | geodesic radius check | 143 | 143 valid, closed, radius error < 0.1% |

**Real NOTAM records exercised: 1,281** (target ≥ 200). Aerodrome location assigned from section headings: 1,065 / 1,134 (93.9%).

**Caveats:**

- Set B is a round trip. It shows the parser handles real field values and widths, but the text was rendered by our code, not typed by an AIS office.
- The truly independent check (A vs autorouter) covers only 25 NOTAMs.
- Free-text ICAO NOTAMs from FAA/ICAO feeds have not been tested, because the keys are missing.

### 5.2 Classifier (`python -m classification.evaluate` → `evaluation/results/classifier_eval.md`)

> **Current human-label result (21 Nov 2026), frozen hold-out of 101 AAI NOTAMs:** severity macro-F1 0.548 (weak-label baseline) → 0.739 (with human labels), bootstrap 95 % CI of the difference [0.050, 0.350], under-classification 34.7 % → 5.0 %: improvement supported. Category macro-F1 0.763 → 0.733, CI [−0.168, 0.100]: improvement not established. Details in `classification_methodology.md` 6.3.
>
> **Superseded (17 Nov 2026).** The table below pooled 5 CV repeats (650 "predictions" for 130 examples) and included 16 duplicate texts. The corrected protocol, current numbers (weak-label CV, repeat 0: category 0.906, severity 0.891 macro-F1 on 114 de-duplicated examples) and the leakage-safe human-label evaluation are in `classification_methodology.md`. Use those in the report.

Protocol: repeated StratifiedGroupKFold (3 folds × 5 repeats; group = NOTAM identity), with the Q-code **hidden** so the E-text alone is classified. That is the AAI situation.

| Setting | Category macro-F1 | Severity macro-F1 | Severity under-classification |
|---|---|---|---|
| Rules only (Q-code hidden → OTHER / RESTRICTIVE) | 0.000 | 0.081 | 2.3% |
| ML (argmax) | 0.915 (fold 0.903 ± 0.053) | 0.925 (fold 0.916 ± 0.063) | 2.9% |
| **Rules + ML + guard (deployed)** | **0.915** (0.903 ± 0.053) | **0.919** (0.910 ± 0.069) | 2.8% |
| Stricter: folds grouped by text template | 0.901 | 0.929 | — |
| Rules with Q-code visible | 1.0 by construction (circular: the labels *are* the rules) | | |

Per-class F1 for the deployed setting:

| Class | F1 |
|---|---|
| ADVISORY | 0.97 |
| RESTRICTIVE | 0.79 |
| BLOCKING | 1.00 |
| PROCEDURE | 0.99 |
| OBSTACLE | 0.97 |
| AERODROME | 0.88 |
| NAVAID_COMMS | 0.89 |
| RUNWAY | 0.76 |
| NAV_WARNING | 1.00 |

The confusion matrices are in `classifier_eval.md`.

**Interpretation and limits:**

- The 0.80 target is met **against weak labels on autorouter-style text**.
- BLOCKING and NAV_WARNING have only 3 near-duplicate source examples (ISRO launches), so their perfect scores say little.
- Labels come from rules, not humans.
- On AAI texts the model is out of distribution. In the label sheet, for example, a runway-portion closure is predicted as AERODROME.
- The decisive test is the hand-labelled AAI sheet **[to fill once labelled]**. If it falls well below 0.80, report ML as an experiment and rely on rules + guard + the RESTRICTIVE default (plan §7 fallback).

### 5.3 Retrieval (`python -m evaluation.relevance_recall` → `evaluation/results/retrieval_eval.md`)

**Reference:**

- The autorouter NOTAMs whose Item A is the source or destination aerodrome;
- not cancelled or replaced, and valid during the flight;
- ETD 2026-10-16 22:00 UTC (snapshot time), ETA from distance / 450 kt.

**System under test:** retrieval over **AAI-only** events, so the comparison is independent. FL000–350, corridor 200 NM.

| Corridor | Reference | In AAI data | Retrieved of those | Recall end-to-end | Recall algorithmic | Precision (aerodrome-level) |
|---|---|---|---|---|---|---|
| DEL–BOM | 67 | 1 | 1 | 1.5% | 100% | 12.5% |
| DEL–BLR | 57 | 20 | 20 | 35.1% | 100% | 69.0% |
| BOM–MAA | 45 | 5 | 5 | 11.1% | 100% | 83.3% |
| CCU–DEL | 49 | 1 | 1 | 2.0% | 100% | 14.3% |
| DEL–SXR | 33 (VIDP only; VISR not in snapshot) | 1 | 1 | 3.0% | 100% | 14.3% |
| **All** | 251 | 28 | 28 | **11.2%** | **100%** | 49.1% |

**Reading this table honestly:**

- **The relevance logic missed nothing it had** (algorithmic recall 28/28).
- **End-to-end recall is far below the 90% target because of data currency.** The only AAI summary close to the reference date is Chennai, October. Delhi, Mumbai and Kolkata summaries stop at April–July, so most NOTAMs valid on 16 October are simply not in the AAI data.
- **Precision is low for the same reason.** Old summaries contain NOTAMs that were cancelled before October but still look valid.
- **To make this a fair test:** download the current AAI summaries (`python -m ingestion.aai --months 2026-10 2026-11 --save-jsonl`), refresh autorouter on the same day, and re-run with that ETD. **[to fill with the new run]**
- **En-route (FIR) recall** cannot be measured: the autorouter snapshot only contains aerodrome-scoped NOTAMs.

**Runtime:**

- Python reference engine: 1–5 ms per corridor.
- PostGIS: median 17–25 ms per corridor (max 35 ms), well under 500 ms **[measured: PostgreSQL 16.15 + PostGIS 3.4.2 test server, 9 Nov 2026]**. Re-measure on your own PostgreSQL 14.
- SQL and Python reference agree on every NOTAM except 7 corridor-edge cases (spheroid vs sphere).

## 6. What remains for Person A, and why

| Item | Why it is open | What to do |
|---|---|---|
| Live-DB results (migrations on PostGIS, integration tests, SQL timing, geometry checks) | Needs your PostgreSQL 14 + PostGIS | `setup_windows.md` steps 3–9 |
| 48 h unattended scheduler run | Needs your machine running | Step 7 |
| Hand-labelled 300 AAI NOTAMs | Requires human judgement | Fill the CSV, re-run `classification.evaluate` |
| Current AAI summaries + fresh autorouter → fair recall | Repository snapshot is stale | Step 7, then `relevance_recall` |
| FAA / ICAO live data | No API keys | Add keys to `.env`; adapters are ready |
