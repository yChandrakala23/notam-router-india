# Files changed since the 9 Nov 2026 project (17 Nov audit + 21-22 Nov final annotations)

Includes the final annotated sheet `data/labelled/aai_label_sheet.csv` and the frozen split `data/labelled/aai_holdout_split.json`.

```
ADDED    api/routers/plan.py
ADDED    classification/annotations.py
ADDED    classification/experiment.py
ADDED    classification/taxonomy.py
ADDED    data/labelled/aai_holdout_split.json
ADDED    db/migrations/004_classifier_explanation.sql
ADDED    docs/AUDIT_CHANGED_FILES.md
ADDED    docs/RUNNING.md
ADDED    docs/person_a/classification_methodology.md
ADDED    docs/routing_methodology.md
ADDED    evaluation/results/annotation_audit.json
ADDED    evaluation/results/annotation_audit.md
ADDED    evaluation/results/corridor_graphs.geojson
ADDED    evaluation/results/routing_eval.json
ADDED    evaluation/results/routing_eval.md
ADDED    routing/geo.py
ADDED    routing/planner.py
ADDED    tests/conftest.py
ADDED    tests/routing_helpers.py
ADDED    tests/test_annotations.py
ADDED    tests/test_api_plan.py
ADDED    tests/test_candidates.py
ADDED    tests/test_experiment.py
ADDED    tests/test_static_data.py
ADDED    tests/test_taxonomy.py
ADDED    tests/test_training_pipeline.py
MODIFIED README.md
MODIFIED api/main.py
MODIFIED api/relevance.py
MODIFIED api/schemas.py
MODIFIED classification/dataset.py
MODIFIED classification/evaluate.py
MODIFIED classification/merged.py
MODIFIED classification/ml.py
MODIFIED classification/rules.py
MODIFIED classification/train.py
MODIFIED data/labelled/aai_label_sheet.csv
MODIFIED docs/PROGRESS.md
MODIFIED docs/contract.md
MODIFIED docs/person_a/dbms_report.md
MODIFIED docs/person_a/report_sections.md
MODIFIED evaluation/results/classifier_eval.json
MODIFIED evaluation/results/classifier_eval.md
MODIFIED evaluation/results/parser_eval.json
MODIFIED evaluation/results/parser_eval.md
MODIFIED evaluation/results/retrieval_db_check.json
MODIFIED evaluation/results/retrieval_db_check.md
MODIFIED evaluation/results/retrieval_eval.json
MODIFIED evaluation/results/retrieval_eval.md
MODIFIED evaluation/routing_eval.py
MODIFIED ingestion/process.py
MODIFIED routing/candidates.py
MODIFIED routing/conflicts.py
MODIFIED routing/graph.py
MODIFIED routing/select.py
MODIFIED static_data/build_graph.py
MODIFIED static_data/load_airports.py
MODIFIED static_data/load_fir.py
MODIFIED tests/test_conflicts.py
MODIFIED tests/test_db_integration.py
MODIFIED tests/test_select.py
```
