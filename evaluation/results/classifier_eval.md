# Classifier evaluation (generated)

Generated: 2026-11-21T18:28:45+00:00

## How to read this

1. **Weak-label CV** measures how well the E-text reproduces Q-code-derived labels on autorouter-style text. It is in-distribution and NOT an independent accuracy estimate.
2. **Human-labelled AAI evaluation** is the independent test: frozen hold-out, no NOTAM or near-duplicate template on both sides.

## 1. Weak-label CV (Q-code hidden)

Weak examples: 130 raw, 114 after text de-duplication (111 NOTAM identities; sources {'autorouter': 108, 'fixture': 3, 'aai_matched': 3}).

Category distribution: {'PROCEDURE': 45, 'OBSTACLE': 15, 'AERODROME': 32, 'RUNWAY': 14, 'NAVAID_COMMS': 5, 'NAV_WARNING': 3}

Severity distribution: {'ADVISORY': 97, 'RESTRICTIVE': 14, 'BLOCKING': 3}

| Setting | Category macro-F1 (repeat 0) | Category macro-F1 per-repeat mean ± sd | Severity macro-F1 (repeat 0) | Severity macro-F1 per-repeat mean ± sd | Severity under-classification |
|---|---|---|---|---|---|
| rules_only_q_hidden | 0.000 | 0.000 ± 0.000 | 0.073 | 0.073 ± 0.000 | 0.0263 |
| ml_argmax | 0.906 | 0.891 ± 0.012 | 0.891 | 0.925 ± 0.024 | 0.0351 |
| merged_q_hidden | 0.906 | 0.891 ± 0.012 | 0.891 | 0.920 ± 0.019 | 0.0351 |

Stricter grouping by text template:

| Setting | Category macro-F1 (repeat 0) | Category mean ± sd | Severity macro-F1 (repeat 0) | Severity mean ± sd | Under-class |
|---|---|---|---|---|---|
| rules_only_q_hidden | 0.000 | 0.000 ± 0.000 | 0.073 | 0.073 ± 0.000 | 0.0263 |
| ml_argmax | 0.906 | 0.901 ± 0.009 | 0.930 | 0.930 ± 0.000 | 0.0263 |
| merged_q_hidden | 0.906 | 0.901 ± 0.009 | 0.907 | 0.922 ± 0.015 | 0.0263 |

Rules with Q-code visible (sanity, circular): 1.0

### Weak-label CV confusion (repeat 0) - ml_argmax - category

rows = reference, columns = predicted

| | NAV_WARNING | AERODROME | RUNWAY | NAVAID_COMMS | OBSTACLE | PROCEDURE |
|---|---|---|---|---|---|---|
| **NAV_WARNING** | 3 | 0 | 0 | 0 | 0 | 0 |
| **AERODROME** | 0 | 28 | 2 | 0 | 0 | 2 |
| **RUNWAY** | 0 | 4 | 10 | 0 | 0 | 0 |
| **NAVAID_COMMS** | 0 | 0 | 1 | 4 | 0 | 0 |
| **OBSTACLE** | 0 | 1 | 0 | 0 | 14 | 0 |
| **PROCEDURE** | 0 | 0 | 0 | 0 | 0 | 45 |

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| NAV_WARNING | 1.000 | 1.000 | 1.000 | 3 |
| AERODROME | 0.849 | 0.875 | 0.862 | 32 |
| RUNWAY | 0.769 | 0.714 | 0.741 | 14 |
| NAVAID_COMMS | 1.000 | 0.800 | 0.889 | 5 |
| OBSTACLE | 1.000 | 0.933 | 0.966 | 15 |
| PROCEDURE | 0.957 | 1.000 | 0.978 | 45 |

### Weak-label CV confusion (repeat 0) - ml_argmax - severity

rows = reference, columns = predicted

| | BLOCKING | RESTRICTIVE | ADVISORY |
|---|---|---|---|
| **BLOCKING** | 3 | 0 | 0 |
| **RESTRICTIVE** | 0 | 10 | 4 |
| **ADVISORY** | 0 | 4 | 93 |

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| BLOCKING | 1.000 | 1.000 | 1.000 | 3 |
| RESTRICTIVE | 0.714 | 0.714 | 0.714 | 14 |
| ADVISORY | 0.959 | 0.959 | 0.959 | 97 |

### Weak-label CV confusion (repeat 0) - merged_q_hidden - category

rows = reference, columns = predicted

| | NAV_WARNING | AERODROME | RUNWAY | NAVAID_COMMS | OBSTACLE | PROCEDURE |
|---|---|---|---|---|---|---|
| **NAV_WARNING** | 3 | 0 | 0 | 0 | 0 | 0 |
| **AERODROME** | 0 | 28 | 2 | 0 | 0 | 2 |
| **RUNWAY** | 0 | 4 | 10 | 0 | 0 | 0 |
| **NAVAID_COMMS** | 0 | 0 | 1 | 4 | 0 | 0 |
| **OBSTACLE** | 0 | 1 | 0 | 0 | 14 | 0 |
| **PROCEDURE** | 0 | 0 | 0 | 0 | 0 | 45 |

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| NAV_WARNING | 1.000 | 1.000 | 1.000 | 3 |
| AERODROME | 0.849 | 0.875 | 0.862 | 32 |
| RUNWAY | 0.769 | 0.714 | 0.741 | 14 |
| NAVAID_COMMS | 1.000 | 0.800 | 0.889 | 5 |
| OBSTACLE | 1.000 | 0.933 | 0.966 | 15 |
| PROCEDURE | 0.957 | 1.000 | 0.978 | 45 |

### Weak-label CV confusion (repeat 0) - merged_q_hidden - severity

rows = reference, columns = predicted

| | BLOCKING | RESTRICTIVE | ADVISORY |
|---|---|---|---|
| **BLOCKING** | 3 | 0 | 0 |
| **RESTRICTIVE** | 0 | 10 | 4 |
| **ADVISORY** | 0 | 4 | 93 |

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| BLOCKING | 1.000 | 1.000 | 1.000 | 3 |
| RESTRICTIVE | 0.714 | 0.714 | 0.714 | 14 |
| ADVISORY | 0.959 | 0.959 | 0.959 | 97 |

## Human-labelled AAI evaluation (leakage-safe)

Annotated NOTAMs usable: hold-out 101, development 199. Split: {'created_at': '2026-11-21T18:28:57+00:00', 'seed': 13, 'test_frac': 0.3, 'grouping': 'near-duplicate clusters (char 3-5-gram TF-IDF cosine >= 0.8 or same first-6-token template)', 'n_clusters': 227, 'stratified_on': 'severity (category when severity missing)', 'sheet_fingerprint': '2f22fe1ea8f998741fc6bd1ea58b1cfe38b7c7810dfebaf40ccc23cb8c71d78e', 'rare_class_notes': [], 'reused': False}

### Leakage audit (weak training set vs annotated sheet)

- shared NOTAM identities: 1
- shared text templates: 11
- shared exact texts: 5
- Before this protocol, the human-label evaluation trained on ALL weak examples and scored ALL annotated rows, so these overlaps were in both training and test. All shared items are now removed from training whenever they are evaluated.

### Label distributions

- weak (Q-code) training labels: {'category': {'PROCEDURE': 45, 'OBSTACLE': 15, 'AERODROME': 32, 'RUNWAY': 14, 'NAVAID_COMMS': 5, 'NAV_WARNING': 3}, 'severity': {'ADVISORY': 97, 'RESTRICTIVE': 14, 'BLOCKING': 3}}
- development (human): {'category': {'AERODROME': 91, 'OBSTACLE': 8, 'NAV_WARNING': 50, 'NAVAID_COMMS': 18, 'RUNWAY': 21, 'PROCEDURE': 11}, 'severity': {'RESTRICTIVE': 117, 'ADVISORY': 71, 'BLOCKING': 11}}
- hold-out (human): {'category': {'RUNWAY': 20, 'NAVAID_COMMS': 4, 'OBSTACLE': 15, 'NAV_WARNING': 23, 'AERODROME': 30, 'PROCEDURE': 9}, 'severity': {'RESTRICTIVE': 59, 'BLOCKING': 6, 'ADVISORY': 36}}

### Frozen hold-out (each NOTAM predicted once)

| Model | Mode | Cat acc | Cat macro-F1 | Sev acc | Sev macro-F1 | Sev macro-P | Sev macro-R | Sev under-class | NOTAMs |
|---|---|---|---|---|---|---|---|---|---|
| baseline | ml | 0.614 | 0.560 | 0.455 | 0.286 | 0.465 | 0.390 | 0.5446 | 101 |
| baseline | merged | 0.772 | 0.763 | 0.614 | 0.548 | 0.640 | 0.573 | 0.3465 | 101 |
| improved | ml | 0.822 | 0.776 | 0.812 | 0.680 | 0.708 | 0.664 | 0.0891 | 101 |
| improved | merged | 0.812 | 0.733 | 0.812 | 0.739 | 0.736 | 0.757 | 0.0495 | 101 |

Bootstrap (merged, improved - baseline macro-F1 over hold-out NOTAMs): {'category': {'n': 101, 'mean_diff_improved_minus_baseline': -0.028, 'ci95': [-0.1678, 0.0997]}, 'severity': {'n': 101, 'mean_diff_improved_minus_baseline': 0.1891, 'ci95': [0.0504, 0.3495]}}

#### Hold-out confusion — baseline (merged) — category

rows = reference, columns = predicted

| | NAV_WARNING | AERODROME | RUNWAY | NAVAID_COMMS | OBSTACLE | PROCEDURE |
|---|---|---|---|---|---|---|
| **NAV_WARNING** | 13 | 10 | 0 | 0 | 0 | 0 |
| **AERODROME** | 0 | 27 | 2 | 0 | 0 | 1 |
| **RUNWAY** | 0 | 4 | 16 | 0 | 0 | 0 |
| **NAVAID_COMMS** | 2 | 0 | 0 | 2 | 0 | 0 |
| **OBSTACLE** | 0 | 0 | 0 | 0 | 15 | 0 |
| **PROCEDURE** | 0 | 4 | 0 | 0 | 0 | 5 |

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| NAV_WARNING | 0.867 | 0.565 | 0.684 | 23 |
| AERODROME | 0.600 | 0.900 | 0.720 | 30 |
| RUNWAY | 0.889 | 0.800 | 0.842 | 20 |
| NAVAID_COMMS | 1.000 | 0.500 | 0.667 | 4 |
| OBSTACLE | 1.000 | 1.000 | 1.000 | 15 |
| PROCEDURE | 0.833 | 0.556 | 0.667 | 9 |

#### Hold-out confusion — baseline (merged) — severity

rows = reference, columns = predicted

| | BLOCKING | RESTRICTIVE | ADVISORY |
|---|---|---|---|
| **BLOCKING** | 2 | 0 | 4 |
| **RESTRICTIVE** | 2 | 26 | 31 |
| **ADVISORY** | 0 | 2 | 34 |

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| BLOCKING | 0.500 | 0.333 | 0.400 | 6 |
| RESTRICTIVE | 0.929 | 0.441 | 0.598 | 59 |
| ADVISORY | 0.493 | 0.944 | 0.648 | 36 |

#### Hold-out confusion — improved (merged) — category

rows = reference, columns = predicted

| | NAV_WARNING | AERODROME | RUNWAY | NAVAID_COMMS | OBSTACLE | PROCEDURE |
|---|---|---|---|---|---|---|
| **NAV_WARNING** | 22 | 1 | 0 | 0 | 0 | 0 |
| **AERODROME** | 5 | 22 | 3 | 0 | 0 | 0 |
| **RUNWAY** | 0 | 2 | 18 | 0 | 0 | 0 |
| **NAVAID_COMMS** | 2 | 1 | 0 | 1 | 0 | 0 |
| **OBSTACLE** | 0 | 0 | 0 | 0 | 15 | 0 |
| **PROCEDURE** | 3 | 1 | 0 | 1 | 0 | 4 |

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| NAV_WARNING | 0.688 | 0.957 | 0.800 | 23 |
| AERODROME | 0.815 | 0.733 | 0.772 | 30 |
| RUNWAY | 0.857 | 0.900 | 0.878 | 20 |
| NAVAID_COMMS | 0.500 | 0.250 | 0.333 | 4 |
| OBSTACLE | 1.000 | 1.000 | 1.000 | 15 |
| PROCEDURE | 1.000 | 0.444 | 0.615 | 9 |

#### Hold-out confusion — improved (merged) — severity

rows = reference, columns = predicted

| | BLOCKING | RESTRICTIVE | ADVISORY |
|---|---|---|---|
| **BLOCKING** | 4 | 2 | 0 |
| **RESTRICTIVE** | 4 | 52 | 3 |
| **ADVISORY** | 0 | 10 | 26 |

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| BLOCKING | 0.500 | 0.667 | 0.571 | 6 |
| RESTRICTIVE | 0.812 | 0.881 | 0.846 | 59 |
| ADVISORY | 0.897 | 0.722 | 0.800 | 36 |

### Development cross-validation (identical folds for both models)

5-fold StratifiedGroupKFold x 5 repeats on 199 NOTAMs; per-repeat metrics; each repeat predicts each development NOTAM exactly once.

| Model | Category macro-F1 mean ± sd | Severity macro-F1 mean ± sd |
|---|---|---|
| baseline | 0.509 ± 0.030 | 0.364 ± 0.002 |
| improved | 0.567 ± 0.012 | 0.587 ± 0.009 |

Paired difference (improved - baseline): {'category': {'mean_diff': 0.0571, 'sd': 0.0281, 'repeats_improved_better': 5, 'repeats': 5}, 'severity': {'mean_diff': 0.2226, 'sd': 0.0103, 'repeats_improved_better': 5, 'repeats': 5}}

Severity threshold sensitivity (ML severity, low confidence -> RESTRICTIVE): {'baseline': {'0.4': 0.2466, '0.5': 0.2487, '0.55': 0.2651, '0.6': 0.259, '0.7': 0.2834}, 'improved': {'0.4': 0.7468, '0.5': 0.5881, '0.55': 0.59, '0.6': 0.5835, '0.7': 0.5545}}

### Verdict

category: hold-out macro-F1 0.7633 -> 0.7331; dev-CV paired diff +0.0571 (better in 5/5 repeats); bootstrap 95% CI [-0.1678, 0.0997] => improvement NOT established | severity: hold-out macro-F1 0.5484 -> 0.739; dev-CV paired diff +0.2226 (better in 5/5 repeats); bootstrap 95% CI [0.0504, 0.3495] => improvement supported
