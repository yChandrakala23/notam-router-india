"""Train the E-text fallback model and (optionally) export a hand-labelling sheet.

Owner: Person A.

    python -m classification.train                        # weak + human labels, hold-out excluded
    python -m classification.train --labels weak          # baseline (weak Q-code labels only)
    python -m classification.train --use-holdout          # final model on ALL valid labels
    python -m classification.train --export-label-sheet   # write a 300-row CSV to annotate

Training data
-------------
* weak Q-code labels (classification.dataset.build_weak_dataset), and
* validated, de-duplicated human AAI labels (classification.annotations),
  each example tagged with its source and label type.  Category and severity
  are fitted independently, so a row with only one valid label still counts
  for that field.

By default the frozen evaluation hold-out (data/labelled/aai_holdout_split.json)
is kept out of training so that classification.evaluate stays a fair test.
``--use-holdout`` trains on everything for deployment; the metadata then says
that the hold-out numbers no longer apply to that model.

The model file is git-ignored (derived from commercial autorouter text).
"""

from __future__ import annotations

import argparse
import collections
import csv
import random
from datetime import datetime, timezone

from classification.dataset import LABEL_SHEET, build_weak_dataset, unlabelled_aai
from classification.merged import classify
from classification.ml import MODEL_PATH, NotamTextModel


def train(save: bool = True, labels: str = "weak+human", use_holdout: bool = False,
          path=MODEL_PATH) -> NotamTextModel:
    import sklearn

    from classification.dataset import combine_examples, human_examples
    from classification.experiment import SPLIT_PATH, make_holdout
    from classification.ml import model_config

    weak = build_weak_dataset()
    human, report = human_examples() if labels == "weak+human" else ([], None)
    exclude_groups = exclude_templates = frozenset()
    holdout_info = "not applicable (no human labels)"
    leakage_removed = 0
    if human and not use_holdout:
        from classification.experiment import _cluster, similarity_clusters

        split = make_holdout(human)
        hold = set(split["holdout_identities"])
        held = [e for e in human if e.group in hold]
        # Same exclusion as the evaluation: identity, template and near-duplicate
        # cluster, so the hold-out scores apply to exactly this model.
        clusters = similarity_clusters(list(weak) + list(human))
        banned = {_cluster(e, clusters) for e in held}
        before = len(weak) + len(human)
        weak = [e for e in weak if _cluster(e, clusters) not in banned]
        human = [e for e in human if _cluster(e, clusters) not in banned]
        leakage_removed = before - len(weak) - len(human)
        exclude_groups = frozenset(e.group for e in held)
        exclude_templates = frozenset(e.template for e in held)
        holdout_info = (f"{len(hold)} hold-out NOTAMs and their near-duplicate clusters excluded "
                        f"({leakage_removed} examples removed; {SPLIT_PATH.name})")
    elif human:
        holdout_info = "hold-out INCLUDED in training: hold-out metrics do not apply to this model"
    examples, merge = combine_examples(weak, human, exclude_groups, exclude_templates)
    if len(examples) < 10:
        raise SystemExit(
            f"Only {len(examples)} training examples found. Put autorouter snapshots in "
            "data/autorouter/ (python -m ingestion.autorouter) and/or annotate the label sheet.")

    def dist(field):
        return dict(collections.Counter(getattr(e, field) for e in examples if getattr(e, field)))

    minority = {f: [c for c, n in dist(f).items() if n < 5] for f in ("category", "severity")}
    model = NotamTextModel(meta={
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "label_mode": labels,
        "holdout": holdout_info,
        "n_train": len(examples),
        "sources": dict(collections.Counter(e.source for e in examples)),
        "label_types": dict(collections.Counter(e.label_type for e in examples)),
        "category_counts": dist("category"),
        "severity_counts": dist("severity"),
        "minority_classes_lt5": minority,
        "dedup": {"text_duplicates_removed": merge.text_duplicates_removed,
                  "weak_dropped_same_identity_as_human": merge.dropped_weak_same_identity,
                  "weak_human_disagreements": len(merge.weak_human_disagreements),
                  "same_text_conflicts": len(merge.same_text_conflicts)},
        "annotation_summary": report.summary() if report else None,
        "config": model_config(),
        "sklearn_version": sklearn.__version__,
    })
    model.fit([e.text for e in examples], [e.category for e in examples], [e.severity for e in examples])
    if save:
        print(f"Saved model to {model.save(path)}")
    for key in ("label_mode", "holdout", "n_train", "sources", "label_types",
                "category_counts", "severity_counts", "minority_classes_lt5", "dedup"):
        print(f"{key}: {model.meta[key]}")
    if any(minority.values()):
        print("NOTE: classes with < 5 examples are learned from very little data; "
              "their scores are unreliable (see classifier_eval.md per-class support).")
    return model


def export_label_sheet(model: NotamTextModel, n: int = 300, seed: int = 7) -> None:
    """Write a CSV of AAI NOTAMs for hand-correction (public AAI text only)."""
    items = unlabelled_aai()
    by_region = collections.defaultdict(list)
    for item in items:
        by_region[item.nof].append(item)
    rng = random.Random(seed)
    for group in by_region.values():
        rng.shuffle(group)
    chosen, regions = [], sorted(by_region)
    while len(chosen) < min(n, len(items)):
        for region in regions:
            if by_region[region] and len(chosen) < n:
                chosen.append(by_region[region].pop())

    if LABEL_SHEET.exists():
        raise SystemExit(f"{LABEL_SHEET} already exists - not overwriting hand labels.")
    LABEL_SHEET.parent.mkdir(parents=True, exist_ok=True)
    with LABEL_SHEET.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["nof", "notam_id", "location", "e_text",
                         "pred_category", "pred_severity", "pred_method", "pred_conf",
                         "human_category", "human_severity", "notes"])
        for item in chosen:
            pred = classify(None, item.e_text, model=model)
            writer.writerow([item.nof, item.notam_id, item.location or "", item.e_text,
                             pred.category, pred.severity, pred.method, pred.confidence,
                             "", "", ""])
    print(f"Wrote {len(chosen)} rows to {LABEL_SHEET}. Fill human_category / human_severity.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Train NOTAM E-text classifier")
    parser.add_argument("--labels", choices=["weak", "weak+human"], default="weak+human")
    parser.add_argument("--use-holdout", action="store_true",
                        help="also train on the frozen hold-out (final deployment model)")
    parser.add_argument("--export-label-sheet", action="store_true")
    parser.add_argument("--n", type=int, default=300)
    args = parser.parse_args(argv)
    model = train(labels=args.labels, use_holdout=args.use_holdout)
    if args.export_label_sheet:
        export_label_sheet(model, args.n)


if __name__ == "__main__":
    main()
