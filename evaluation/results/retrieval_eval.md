# Retrieval evaluation (generated)

ETD 2026-10-16T22:00:00+00:00, ETA = ETD + distance/450 kt, FL000-350, corridor 200.0 NM.

AAI summary months available per NOF: {'VOMM': ['2026-03', '2026-04', '2026-05', '2026-06', '2026-10'], 'VIDP': ['2026-04', '2026-05', '2026-06', '2026-07'], 'VECC': ['2026-04', '2026-05', '2026-06'], 'VABB': ['2026-04', '2026-05', '2026-06']}

| Corridor | reference (autorouter, aerodrome) | in AAI data | TP | recall end-to-end | recall algorithmic | aerodrome-level retrieved | precision (aerodrome) | total retrieved |
|---|---|---|---|---|---|---|---|---|
| DEL-BOM | 67 | 1 | 1 | 1.5% | 100.0% | 8 | 12.5% | 9 {'AERODROME': 8, 'CORRIDOR': 1} |
| DEL-BLR | 57 | 20 | 20 | 35.1% | 100.0% | 29 | 69.0% | 120 {'FIR_WIDE': 39, 'AERODROME': 29, 'CORRIDOR': 52} |
| BOM-MAA | 45 | 5 | 5 | 11.1% | 100.0% | 6 | 83.3% | 90 {'FIR_WIDE': 39, 'AERODROME': 6, 'CORRIDOR': 45} |
| CCU-DEL | 49 | 1 | 1 | 2.0% | 100.0% | 7 | 14.3% | 16 {'AERODROME': 7, 'CORRIDOR': 9} |
| DEL-SXR | 33 | 1 | 1 | 3.0% | 100.0% | 7 | 14.3% | 8 {'AERODROME': 7, 'CORRIDOR': 1} |

Summary: {"recall_end_to_end": 0.1116, "data_coverage": 0.1116, "recall_algorithmic": 1.0, "precision_aerodrome_level": 0.4912, "reference": 251, "in_aai_data": 28, "true_positives": 28, "retrieved_aerodrome_level": 57, "aerodrome_tp": 28, "algorithmic_hits": 28}

## PostGIS query time

| Corridor | features | median ms | max ms |
|---|---|---|---|
| DEL-BOM | 75 | 23.9 | 29.8 |
| DEL-BLR | 169 | 29.2 | 39.6 |
| BOM-MAA | 148 | 39.2 | 95.5 |
| CCU-DEL | 64 | 35.7 | 36.7 |
| DEL-SXR | 40 | 33.8 | 34.5 |