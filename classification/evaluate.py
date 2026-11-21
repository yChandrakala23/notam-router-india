"""Evaluate the merged classifier.

Owner: Person A.

    python -m classification.evaluate

Writes evaluation/results/classifier_eval.json and classifier_eval.md.

What is measured (and what is not)
----------------------------------
* Reference labels are **weak labels** derived from Q-codes by the stage-1
  rules (see classification/dataset.py).  Scoring the rules against their own
  labels is circular, so "rules with Q-code" is reported only as a sanity
  check (it is 1.0 by construction).
* The informative comparison simulates NOTAMs **without a usable Q-code**
  (the AAI summary situation): the Q-code is hidden and the system must decide
  from the E-text.

    rules-only (Q hidden)   -> category OTHER, severity RESTRICTIVE (default)
    ML (argmax)             -> TF-IDF + LR prediction
    merged (Q hidden)       -> ML + low-confidence default + keyword guard

* Cross-validation: repeated StratifiedGroupKFold (group = NOTAM identity),
  so the same NOTAM seen by two sources never sits in train and test.
* "Under-classification" = predicted severity less severe than the reference
  (the unsafe direction for routing).
* Repeated CV: confusion matrices and per-class tables come from repeat 0
  only (one prediction per NOTAM); variability is reported per repeat.  The
  earlier version pooled 5 repeats (650 "predictions" for 130 examples),
  which overstated the sample size.
* Weak examples are de-duplicated by text before CV (16 of 130 were exact
  duplicates, mostly one NOTAM seen through two sources).
* Human AAI labels: leakage-safe hold-out + development CV comparing the
  baseline and the improved model (classification/experiment.py).  This
  replaces the earlier human-label check, which trained on all weak data and
  scored every annotated row.
"""

from __future__ import annotations

import json
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from classification.dataset import build_weak_dataset, combine_examples, human_examples
from classification.merged import classify
from classification.ml import NotamTextModel, clean_text
from classification.rules import CATEGORIES, SEVERITIES, SEVERITY_RANK, classify_qcode

RESULTS = Path(__file__).resolve().parent.parent / "evaluation" / "results"


def _metrics(y_true, y_pred, labels):
    from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                                 precision_recall_fscore_support)

    present = [l for l in labels if l in set(y_true) | set(y_pred)]
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=present,
                                                 zero_division=0)
    true_labels = [l for l in present if l in set(y_true)]
    return {
        "n": len(y_true),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        # macro-F1 over classes that occur in the reference labels
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=true_labels,
                                         average="macro", zero_division=0)), 4),
        "per_class": {l: {"precision": round(float(pp), 4), "recall": round(float(rr), 4),
                          "f1": round(float(ff), 4), "support": int(ss)}
                      for l, pp, rr, ff, ss in zip(present, p, r, f, s)},
        "labels": present,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=present).tolist(),
    }


def _under(y_true, y_pred):
    pairs = [(t, p) for t, p in zip(y_true, y_pred) if t in SEVERITY_RANK and p in SEVERITY_RANK]
    if not pairs:
        return None
    return round(sum(SEVERITY_RANK[p] < SEVERITY_RANK[t] for t, p in pairs) / len(pairs), 4)


def template_key(text: str, n_tokens: int = 6) -> str:
    """Near-duplicate key: first tokens of the cleaned E-text (templated NOTAMs)."""
    return " ".join(clean_text(text).split()[:n_tokens])


def cross_validate(examples, n_splits=3, repeats=5, grouping="identity"):
    """Weak-label CV with the Q-code hidden (in-distribution, NOT independent)."""
    from sklearn.metrics import f1_score
    from sklearn.model_selection import StratifiedGroupKFold

    texts = np.array([e.text for e in examples], dtype=object)
    cats = np.array([e.category for e in examples])
    sevs = np.array([e.severity for e in examples])
    groups = np.array([template_key(e.text) if grouping == "template" else e.group for e in examples])

    names = ("rules_only_q_hidden", "ml_argmax", "merged_q_hidden")
    repeat_scores = {k: {"cat": [], "sev": []} for k in names}
    repeat0 = {}
    for repeat in range(repeats):
        pred = {k: [None] * len(examples) for k in names}
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=repeat)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            splits = list(splitter.split(texts, cats, groups))
        for train_idx, test_idx in splits:
            model = NotamTextModel().fit(texts[train_idx], cats[train_idx], sevs[train_idx])
            test_texts = list(texts[test_idx])
            preds = model.predict(test_texts)
            merged = [classify(None, t, model=model) for t in test_texts]
            for j, i in enumerate(test_idx):
                pred["rules_only_q_hidden"][i] = ("OTHER", "RESTRICTIVE")
                pred["ml_argmax"][i] = (preds[j].category, preds[j].severity)
                pred["merged_q_hidden"][i] = (merged[j].category, merged[j].severity)
        for name in names:
            cp = [p[0] for p in pred[name]]
            sp = [p[1] for p in pred[name]]
            repeat_scores[name]["cat"].append(
                f1_score(cats, cp, labels=sorted(set(cats)), average="macro", zero_division=0))
            repeat_scores[name]["sev"].append(
                f1_score(sevs, sp, labels=sorted(set(sevs)), average="macro", zero_division=0))
            if repeat == 0:
                repeat0[name] = (cp, sp)

    report = {}
    for name in names:
        cp, sp = repeat0[name]
        report[name] = {
            "category": _metrics(list(cats), cp, list(CATEGORIES)),
            "severity": _metrics(list(sevs), sp, list(SEVERITIES)),
            "severity_under_classification_rate": _under(list(sevs), sp),
            "repeat_macro_f1_category_mean": round(float(np.mean(repeat_scores[name]["cat"])), 4),
            "repeat_macro_f1_category_std": round(float(np.std(repeat_scores[name]["cat"])), 4),
            "repeat_macro_f1_severity_mean": round(float(np.mean(repeat_scores[name]["sev"])), 4),
            "repeat_macro_f1_severity_std": round(float(np.std(repeat_scores[name]["sev"])), 4),
        }
    return report


def rules_sanity(examples):
    ok = sum(
        1 for e in examples
        if (r := classify_qcode(e.q_code)) and (r.category, r.severity) == (e.category, e.severity)
    )
    return {"n": len(examples), "agreement": round(ok / len(examples), 4) if examples else None,
            "note": "circular: weak labels are produced by these rules"}


def _table(m: dict) -> list[str]:
    lines = ["rows = reference, columns = predicted", "",
             "| | " + " | ".join(m["labels"]) + " |", "|---" * (len(m["labels"]) + 1) + "|"]
    for label, row in zip(m["labels"], m["confusion_matrix"]):
        lines.append(f"| **{label}** | " + " | ".join(str(v) for v in row) + " |")
    lines += ["", "| class | precision | recall | F1 | support |", "|---|---|---|---|---|"]
    for label, pc in m["per_class"].items():
        lines.append(f"| {label} | {pc['precision']:.3f} | {pc['recall']:.3f} | {pc['f1']:.3f} | {pc['support']} |")
    return lines + [""]


def _fmt(v):
    return "n/a" if v is None else f"{v:.3f}"


def human_markdown(h: dict) -> list[str]:
    if "status" in h:
        return ["## Human-labelled AAI evaluation", "", f"**{h['status']}**", ""]
    la = h["leakage_audit"]
    lines = ["## Human-labelled AAI evaluation (leakage-safe)", "",
             f"Annotated NOTAMs usable: hold-out {h['holdout_notams']}, development {h['dev_notams']}. "
             f"Split: {h['split']}", "",
             "### Leakage audit (weak training set vs annotated sheet)", "",
             f"- shared NOTAM identities: {la['shared_notam_identities']}",
             f"- shared text templates: {la['shared_text_templates']}",
             f"- shared exact texts: {la['shared_exact_texts']}",
             f"- {la['note']} All shared items are now removed from training whenever they are evaluated.", "",
             "### Label distributions", "",
             f"- weak (Q-code) training labels: {h['weak_distribution']}",
             f"- development (human): {h['dev_distribution']}",
             f"- hold-out (human): {h['holdout_distribution']}", ""]
    if "holdout" in h:
        lines += ["### Frozen hold-out (each NOTAM predicted once)", "",
                  "| Model | Mode | Cat acc | Cat macro-F1 | Sev acc | Sev macro-F1 | Sev macro-P | Sev macro-R "
                  "| Sev under-class | NOTAMs |", "|---|---|---|---|---|---|---|---|---|---|"]
        for v in ("baseline", "improved"):
            for mode in ("ml", "merged"):
                c, sv = h["holdout"][v][mode]["category"], h["holdout"][v][mode]["severity"]
                lines.append(f"| {v} | {mode} | {_fmt(c['accuracy'])} | {_fmt(c['macro_f1'])} | {_fmt(sv['accuracy'])} | "
                             f"{_fmt(sv['macro_f1'])} | {_fmt(sv['macro_precision'])} | {_fmt(sv['macro_recall'])} | "
                             f"{sv.get('under_classification_rate')} | {sv['n_unique_notams']} |")
        lines += ["", f"Bootstrap (merged, improved - baseline macro-F1 over hold-out NOTAMs): {h['holdout_bootstrap']}", ""]
        for v in ("baseline", "improved"):
            for kind in ("category", "severity"):
                lines += [f"#### Hold-out confusion — {v} (merged) — {kind}", ""] + _table(h["holdout"][v]["merged"][kind])
    cv = h["dev_cv"]
    if "summary" in cv:
        lines += ["### Development cross-validation (identical folds for both models)", "",
                  f"{cv['folds']}-fold StratifiedGroupKFold x {cv['repeats']} repeats on {cv['n_dev_notams']} NOTAMs; {cv['note']}.", "",
                  "| Model | Category macro-F1 mean ± sd | Severity macro-F1 mean ± sd |", "|---|---|---|"]
        for v, d in cv["summary"].items():
            lines.append(f"| {v} | {d['category_macro_f1_mean']:.3f} ± {d['category_macro_f1_sd']:.3f} | "
                         f"{d['severity_macro_f1_mean']:.3f} ± {d['severity_macro_f1_sd']:.3f} |")
        lines += ["", f"Paired difference (improved - baseline): {cv['paired_difference']}", "",
                  f"Severity threshold sensitivity (ML severity, low confidence -> RESTRICTIVE): "
                  f"{cv['severity_threshold_sensitivity_ml_only']}", ""]
    else:
        lines += [f"Development CV: {cv.get('status')}", ""]
    lines += ["### Verdict", "", h["verdict"], ""]
    return lines


def to_markdown(result) -> str:
    d = result["dataset"]
    lines = ["# Classifier evaluation (generated)", "", f"Generated: {result['generated_at']}", "",
             "## How to read this", "",
             "1. **Weak-label CV** measures how well the E-text reproduces Q-code-derived labels on "
             "autorouter-style text. It is in-distribution and NOT an independent accuracy estimate.",
             "2. **Human-labelled AAI evaluation** is the independent test: frozen hold-out, no NOTAM or "
             "near-duplicate template on both sides.", "",
             f"## 1. Weak-label CV (Q-code hidden)", "",
             f"Weak examples: {d['n_raw']} raw, {d['n']} after text de-duplication "
             f"({d['groups']} NOTAM identities; sources {d['sources']}).", "",
             f"Category distribution: {d['categories']}", "", f"Severity distribution: {d['severities']}", "",
             "| Setting | Category macro-F1 (repeat 0) | Category macro-F1 per-repeat mean ± sd "
             "| Severity macro-F1 (repeat 0) | Severity macro-F1 per-repeat mean ± sd | Severity under-classification |",
             "|---|---|---|---|---|---|"]
    for grouping in ("cross_validation", "cross_validation_template_grouped"):
        if grouping == "cross_validation_template_grouped":
            lines += ["", "Stricter grouping by text template:", "",
                      "| Setting | Category macro-F1 (repeat 0) | Category mean ± sd | Severity macro-F1 (repeat 0) | Severity mean ± sd | Under-class |",
                      "|---|---|---|---|---|---|"]
        for name, r in result[grouping].items():
            lines.append(
                f"| {name} | {r['category']['macro_f1']:.3f} | {r['repeat_macro_f1_category_mean']:.3f} ± "
                f"{r['repeat_macro_f1_category_std']:.3f} | {r['severity']['macro_f1']:.3f} | "
                f"{r['repeat_macro_f1_severity_mean']:.3f} ± {r['repeat_macro_f1_severity_std']:.3f} | "
                f"{r['severity_under_classification_rate']} |")
    lines += ["", f"Rules with Q-code visible (sanity, circular): {result['rules_with_qcode']['agreement']}", ""]
    for name in ("ml_argmax", "merged_q_hidden"):
        for field in ("category", "severity"):
            lines += [f"### Weak-label CV confusion (repeat 0) - {name} - {field}", ""]
            lines += _table(result["cross_validation"][name][field])
    lines += human_markdown(result["human_labels"])
    return "\n".join(lines)


def main(argv=None):
    import argparse

    from classification import experiment
    from classification.annotations import main as audit_main

    parser = argparse.ArgumentParser(description="Evaluate the NOTAM classifier")
    parser.add_argument("--resplit", action="store_true", help="redraw the frozen AAI hold-out")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)

    raw = build_weak_dataset()
    if not raw:
        raise SystemExit("No weak-labelled data (data/autorouter/ is empty).")
    examples, merge = combine_examples(raw, [])
    human, _ = human_examples()
    audit_main([])
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "n_raw": len(raw), "n": len(examples),
            "text_duplicates_removed": merge.text_duplicates_removed,
            "groups": len({e.group for e in examples}),
            "sources": dict(Counter(e.source for e in examples)),
            "categories": dict(Counter(e.category for e in examples)),
            "severities": dict(Counter(e.severity for e in examples)),
        },
        "protocol": ("weak: StratifiedGroupKFold(3) x 5 repeats, metrics from repeat 0 + per-repeat spread; "
                     "human: see classification/experiment.py"),
        "rules_with_qcode": rules_sanity(examples),
        "cross_validation": cross_validate(examples, grouping="identity"),
        "cross_validation_template_grouped": cross_validate(examples, grouping="template"),
        "human_labels": experiment.run(examples, human, resplit=args.resplit, repeats=args.repeats),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "classifier_eval.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (RESULTS / "classifier_eval.md").write_text(to_markdown(result), encoding="utf-8")
    for name, r in result["cross_validation"].items():
        print(f"[weak CV] {name:22s} cat {r['category']['macro_f1']:.3f}  sev {r['severity']['macro_f1']:.3f}")
    h = result["human_labels"]
    print("[human]", h.get("status") or h.get("verdict"))
    print(f"Wrote {RESULTS / 'classifier_eval.md'}")


if __name__ == "__main__":
    main()
