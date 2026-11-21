"""Leakage-safe evaluation of the text classifier against human AAI labels.

Owner: Person A.   Called by ``python -m classification.evaluate``.

Models compared (same features and classifier; only the training data differs)
----------------------------------------------------------------------------
baseline   TF-IDF + LR trained on weak Q-code labels only (the original model)
improved   the same pipeline trained on weak labels + human AAI labels from the
           development part of the sheet

Protocol
--------
1. Annotations are validated (classification.annotations): missing / invalid /
   conflicting labels are excluded per field; one example per NOTAM identity.
2. Leakage audit: identities, text templates and exact texts shared between the
   weak training set and the annotated AAI sheet are counted and reported.
3. A **frozen hold-out** (default 30 % of annotated NOTAMs) is drawn once with
   StratifiedGroupKFold, grouping by text template (near-duplicate NOTAMs stay
   on one side) and stratifying by severity.  It is saved to
   data/labelled/aai_holdout_split.json and reused, so results are reproducible
   and the hold-out is never used for training or tuning.
4. Every model evaluated on a set is trained with that set's identities and
   templates removed from its training data (weak and human), so no NOTAM and
   no near-duplicate template appears on both sides.
5. Development CV: repeated StratifiedGroupKFold on the development part only;
   baseline and improved use the *identical* folds.  Each repeat predicts every
   development NOTAM once; metrics are reported per repeat (mean ± sd).  Pooled
   predictions across repeats are NOT presented as independent samples; the
   confusion matrix shown is from repeat 0 (one prediction per NOTAM).
6. Hold-out: both models are trained on all their allowed data and scored once
   on the hold-out.  A bootstrap over hold-out NOTAMs gives a 95 % interval for
   the macro-F1 difference.
"""

from __future__ import annotations

import hashlib
import json
import random
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from classification.dataset import Example, combine_examples
from classification.merged import classify
from classification.ml import LOW_CONFIDENCE, NotamTextModel
from classification.taxonomy import CATEGORIES, SEVERITIES, SEVERITY_RANK

ROOT = Path(__file__).resolve().parent.parent
SPLIT_PATH = ROOT / "data" / "labelled" / "aai_holdout_split.json"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def metrics(y_true: list[str], y_pred: list[str], labels, identities: Optional[list[str]] = None) -> dict:
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

    present = [l for l in labels if l in set(y_true) | set(y_pred)]
    ref = [l for l in labels if l in set(y_true)]
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=present, zero_division=0)
    out = {
        "n_predictions": len(y_true),
        "n_unique_notams": len(set(identities)) if identities is not None else None,
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4) if y_true else None,
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=ref, average="macro", zero_division=0)), 4) if y_true else None,
        "macro_precision": round(float(np.mean([pp for l, pp in zip(present, p) if l in ref])), 4) if ref else None,
        "macro_recall": round(float(np.mean([rr for l, rr in zip(present, r) if l in ref])), 4) if ref else None,
        "per_class": {l: {"precision": round(float(pp), 4), "recall": round(float(rr), 4),
                          "f1": round(float(ff), 4), "support": int(ss)}
                      for l, pp, rr, ff, ss in zip(present, p, r, f, s)},
        "labels": present,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=present).tolist() if y_true else [],
        "classes_absent_from_reference": [l for l in labels if l not in set(y_true)],
    }
    if set(labels) == set(SEVERITIES) and y_true:
        out["under_classification_rate"] = round(
            sum(SEVERITY_RANK[pp] < SEVERITY_RANK[t] for t, pp in zip(y_true, y_pred)) / len(y_true), 4)
    return out


def _macro_f1(y_true, y_pred) -> float:
    from sklearn.metrics import f1_score

    return float(f1_score(y_true, y_pred, labels=sorted(set(y_true)), average="macro", zero_division=0))


# ---------------------------------------------------------------------------
# Near-duplicate clusters
# ---------------------------------------------------------------------------

NEAR_DUP_THRESHOLD = 0.8


def _tfidf_matrix(texts):
    from sklearn.feature_extraction.text import TfidfVectorizer

    from classification.ml import clean_text

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, lowercase=False)
    return vec, vec.fit_transform([clean_text(t) for t in texts])


def similarity_clusters(examples: list[Example], threshold: float = NEAR_DUP_THRESHOLD) -> dict[str, str]:
    """Map each normalised text to a near-duplicate cluster id.

    Texts are joined when their character 3-5-gram TF-IDF cosine similarity is
    >= ``threshold`` or when they share the first-6-token template.  Clusters
    are the connected components (union-find), so a NOTAM family re-issued
    with new dates or a different first line stays together.
    """
    from classification.ml import clean_text

    texts = sorted({clean_text(e.text) for e in examples})
    if not texts:
        return {}
    parent = list(range(len(texts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    _, X = _tfidf_matrix(texts)
    sims = (X @ X.T).tocoo()
    for i, j, v in zip(sims.row, sims.col, sims.data):
        if i < j and v >= threshold:
            union(i, j)
    first = {}
    from classification.annotations import template_key

    for i, t in enumerate(texts):
        key = template_key(t)
        if key in first:
            union(i, first[key])
        else:
            first[key] = i
    return {t: f"C{find(i):04d}" for i, t in enumerate(texts)}


def _cluster(e: Example, clusters: Optional[dict]) -> str:
    if not clusters:
        return e.template
    from classification.ml import clean_text

    return clusters.get(clean_text(e.text), e.template)


def novelty(eval_examples: list[Example], train_examples: list[Example]) -> list[float]:
    """Max cosine similarity of each evaluated text to any training text."""
    if not train_examples:
        return [0.0] * len(eval_examples)
    from classification.ml import clean_text

    vec, X = _tfidf_matrix([e.text for e in train_examples])
    Y = vec.transform([clean_text(e.text) for e in eval_examples])
    return [float(v) for v in (Y @ X.T).max(axis=1).toarray().ravel()]


# ---------------------------------------------------------------------------
# Leakage audit and hold-out split
# ---------------------------------------------------------------------------


def leakage_audit(weak: list[Example], human: list[Example]) -> dict:
    from classification.ml import clean_text

    hg = {e.group for e in human}
    ht = {e.template for e in human}
    hx = {clean_text(e.text) for e in human}
    shared_groups = sorted({e.group for e in weak} & hg)
    shared_templates = sorted({e.template for e in weak} & ht)
    shared_texts = {clean_text(e.text) for e in weak} & hx
    return {
        "annotated_notams": len(hg),
        "weak_examples": len(weak),
        "shared_notam_identities": len(shared_groups),
        "shared_identity_list": shared_groups[:50],
        "shared_text_templates": len(shared_templates),
        "shared_exact_texts": len(shared_texts),
        "note": ("Before this protocol, the human-label evaluation trained on ALL weak examples and "
                 "scored ALL annotated rows, so these overlaps were in both training and test."),
    }


def _sheet_fingerprint(human: list[Example]) -> str:
    payload = "\n".join(sorted(f"{e.group}|{e.category}|{e.severity}" for e in human))
    return hashlib.sha256(payload.encode()).hexdigest()


def make_holdout(human: list[Example], test_frac: float = 0.3, seed: int = 13,
                 path: Path = SPLIT_PATH, resplit: bool = False, clusters: Optional[dict] = None) -> dict:
    """Frozen hold-out of annotated NOTAM identities (grouped by template)."""
    from sklearn.model_selection import StratifiedGroupKFold

    identities = sorted({e.group for e in human})
    if path.exists() and not resplit:
        saved = json.loads(path.read_text(encoding="utf-8"))
        known = set(saved["holdout_identities"]) | set(saved["dev_identities"])
        new = [i for i in identities if i not in known]
        saved["new_identities_assigned_to_dev"] = new
        saved["dev_identities"] = sorted(set(saved["dev_identities"]) | set(new))
        saved["holdout_identities"] = sorted(set(saved["holdout_identities"]) & set(identities))
        saved["dev_identities"] = sorted(set(saved["dev_identities"]) & set(identities))
        saved["reused"] = True
        return saved

    by_id = {e.group: e for e in human}
    ids = np.array(identities)
    clusters = clusters if clusters is not None else similarity_clusters(human)
    groups = np.array([_cluster(by_id[i], clusters) for i in identities])
    strat = np.array([by_id[i].severity or by_id[i].category or "NA" for i in identities])
    n_splits = min(max(2, round(1 / test_frac)), len(set(groups)))
    if n_splits < 2:
        raise ValueError("need at least two distinct text templates to draw a hold-out")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, test_idx = next(StratifiedGroupKFold(n_splits=n_splits, shuffle=True,
                                                random_state=seed).split(ids, strat, groups))
    holdout = set(ids[test_idx])

    # Rare classes: make sure a class with >= 2 template groups is represented
    # on both sides when possible; report the rest instead of hiding it.
    notes = []
    for label in sorted(set(strat)):
        members = [i for i in identities if (by_id[i].severity or by_id[i].category) == label]
        tmpl = {_cluster(by_id[i], clusters) for i in members}
        in_hold = [i for i in members if i in holdout]
        if len(tmpl) >= 2 and not in_hold:
            pick = sorted(members)[0]
            moved = {i for i in members if _cluster(by_id[i], clusters) == _cluster(by_id[pick], clusters)}
            holdout |= moved
            notes.append(f"{label}: moved template group of {pick} into hold-out (was absent)")
        elif len(tmpl) < 2:
            notes.append(f"{label}: only {len(tmpl)} near-duplicate cluster(s); cannot be on both sides")
    split = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed, "test_frac": test_frac,
        "grouping": f"near-duplicate clusters (char 3-5-gram TF-IDF cosine >= {NEAR_DUP_THRESHOLD} or same "
                    "first-6-token template)",
        "n_clusters": len(set(groups)),
        "stratified_on": "severity (category when severity missing)",
        "sheet_fingerprint": _sheet_fingerprint(human),
        "holdout_identities": sorted(holdout),
        "dev_identities": sorted(set(identities) - holdout),
        "rare_class_notes": notes, "reused": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(split, indent=1), encoding="utf-8")
    return split


# ---------------------------------------------------------------------------
# Training variants and scoring
# ---------------------------------------------------------------------------


def train_variant(variant: str, weak: list[Example], human_train: list[Example],
                  exclude: list[Example], clusters: Optional[dict] = None) -> tuple[NotamTextModel, dict]:
    groups = frozenset(e.group for e in exclude)
    templates = frozenset(e.template for e in exclude)
    banned = {_cluster(e, clusters) for e in exclude} if clusters else set()
    pre = 0
    if banned:
        keep_w = [e for e in weak if _cluster(e, clusters) not in banned]
        keep_h = [e for e in human_train if _cluster(e, clusters) not in banned]
        pre = (len(weak) - len(keep_w)) + (len(human_train) - len(keep_h))
        weak, human_train = keep_w, keep_h
    data, rep = combine_examples(weak, human_train if variant == "improved" else [], groups, templates)
    rep.excluded_for_leakage += pre
    model = NotamTextModel().fit([e.text for e in data], [e.category for e in data], [e.severity for e in data])
    info = {"n_train": len(data), "by_label_type": dict(Counter(e.label_type for e in data)),
            "excluded_for_leakage": rep.excluded_for_leakage,
            "text_duplicates_removed": rep.text_duplicates_removed}
    return model, info


def predict(model: NotamTextModel, examples: list[Example], threshold: float = LOW_CONFIDENCE) -> dict:
    raw = model.predict([e.text for e in examples])
    merged = [classify(None, e.text, model=model, threshold=threshold) for e in examples]
    return {"ml": [(p.category, p.severity, p.severity_conf) for p in raw],
            "merged": [(c.category, c.severity, c.confidence) for c in merged]}


def score(examples: list[Example], preds: dict) -> dict:
    out = {}
    for mode in ("ml", "merged"):
        out[mode] = {}
        for kind, idx, labels in (("category", 0, CATEGORIES), ("severity", 1, SEVERITIES)):
            pairs = [(getattr(e, kind), p[idx], e.group) for e, p in zip(examples, preds[mode]) if getattr(e, kind)]
            out[mode][kind] = metrics([t for t, _, _ in pairs], [p for _, p, _ in pairs], labels,
                                      [g for _, _, g in pairs])
    return out


def bootstrap_diff(examples, preds_a, preds_b, kind_idx: int, kind: str, n: int = 1000, seed: int = 0) -> dict:
    rows = [(getattr(e, kind), a[kind_idx], b[kind_idx]) for e, a, b in zip(examples, preds_a, preds_b) if getattr(e, kind)]
    if len(rows) < 5:
        return {"n": len(rows), "note": "too few hold-out NOTAMs for a bootstrap"}
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        t = [r[0] for r in sample]
        diffs.append(_macro_f1(t, [r[2] for r in sample]) - _macro_f1(t, [r[1] for r in sample]))
    diffs.sort()
    return {"n": len(rows), "mean_diff_improved_minus_baseline": round(float(np.mean(diffs)), 4),
            "ci95": [round(diffs[int(0.025 * n)], 4), round(diffs[int(0.975 * n) - 1], 4)]}


def dev_cross_validation(weak, dev, n_splits=5, repeats=5, thresholds=(0.4, 0.5, 0.55, 0.6, 0.7),
                         clusters: Optional[dict] = None):
    from sklearn.model_selection import StratifiedGroupKFold

    n_groups = len({_cluster(e, clusters) for e in dev})
    n_splits = min(n_splits, n_groups)
    if len(dev) < 10 or n_splits < 2:
        return {"status": f"only {len(dev)} development NOTAMs in {n_groups} text-template group(s); "
                          "need >= 10 NOTAMs and >= 2 groups"}
    texts = np.array([e.group for e in dev])
    groups = np.array([_cluster(e, clusters) for e in dev])
    strat = np.array([e.severity or e.category or "NA" for e in dev])
    per_repeat = {v: {"category": [], "severity": []} for v in ("baseline", "improved")}
    repeat0 = {}
    sens = {v: {t: [] for t in thresholds} for v in ("baseline", "improved")}
    for rep in range(repeats):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            folds = list(StratifiedGroupKFold(n_splits=n_splits, shuffle=True,
                                              random_state=100 + rep).split(texts, strat, groups))
        preds = {v: [None] * len(dev) for v in per_repeat}
        sev_probs = {v: [None] * len(dev) for v in per_repeat}
        for train_idx, test_idx in folds:
            test = [dev[i] for i in test_idx]
            train = [dev[i] for i in train_idx]
            for variant in per_repeat:
                model, _ = train_variant(variant, weak, train, exclude=test, clusters=clusters)
                p = predict(model, test)
                for j, i in enumerate(test_idx):
                    preds[variant][i] = p["merged"][j]
                    sev_probs[variant][i] = p["ml"][j]       # (category, severity, severity_conf)
        for variant in per_repeat:
            for kind, k in (("category", 0), ("severity", 1)):
                pairs = [(getattr(e, kind), preds[variant][i][k]) for i, e in enumerate(dev) if getattr(e, kind)]
                per_repeat[variant][kind].append(_macro_f1([a for a, _ in pairs], [b for _, b in pairs]))
            for t in thresholds:
                y, yp = [], []
                for i, e in enumerate(dev):
                    if not e.severity:
                        continue
                    _, ml_sev, ml_conf = sev_probs[variant][i]
                    sev = ml_sev if ml_conf >= t else "RESTRICTIVE"
                    y.append(e.severity)
                    yp.append(sev)
                sens[variant][t].append(_macro_f1(y, yp))
            if rep == 0:
                repeat0[variant] = score(dev, {"merged": preds[variant], "ml": preds[variant]})["merged"]
    summary = {}
    for variant, d in per_repeat.items():
        summary[variant] = {f"{k}_macro_f1_mean": round(float(np.mean(v)), 4) for k, v in d.items()}
        summary[variant].update({f"{k}_macro_f1_sd": round(float(np.std(v)), 4) for k, v in d.items()})
        summary[variant]["per_repeat"] = {k: [round(x, 4) for x in v] for k, v in d.items()}
    paired = {}
    for kind in ("category", "severity"):
        diffs = [b - a for a, b in zip(per_repeat["baseline"][kind], per_repeat["improved"][kind])]
        paired[kind] = {"mean_diff": round(float(np.mean(diffs)), 4), "sd": round(float(np.std(diffs)), 4),
                        "repeats_improved_better": sum(d > 0 for d in diffs), "repeats": len(diffs)}
    return {"n_dev_notams": len(dev), "folds": n_splits, "repeats": repeats, "summary": summary,
            "paired_difference": paired, "repeat0_merged_metrics": repeat0,
            "severity_threshold_sensitivity_ml_only": {
                v: {str(t): round(float(np.mean(x)), 4) for t, x in d.items()} for v, d in sens.items()},
            "note": "per-repeat metrics; each repeat predicts each development NOTAM exactly once"}


def run(weak: list[Example], human: list[Example], *, resplit: bool = False,
        repeats: int = 5, split_path: Path = SPLIT_PATH) -> dict:
    if not human:
        return {"status": "no usable human annotations (see evaluation/results/annotation_audit.md)"}
    clusters = similarity_clusters(list(weak) + list(human))
    split = make_holdout(human, path=split_path, resplit=resplit, clusters=clusters)
    hold_ids, dev_ids = set(split["holdout_identities"]), set(split["dev_identities"])
    holdout = [e for e in human if e.group in hold_ids]
    dev = [e for e in human if e.group in dev_ids]
    result = {
        "leakage_audit": leakage_audit(weak, human),
        "split": {k: v for k, v in split.items() if not k.endswith("identities")},
        "near_duplicate_clusters": {"human_notams": len({e.group for e in human}),
                                    "clusters_among_human": len({_cluster(e, clusters) for e in human})},
        "holdout_notams": len(holdout), "dev_notams": len(dev),
        "holdout_distribution": {"category": dict(Counter(e.category for e in holdout if e.category)),
                                 "severity": dict(Counter(e.severity for e in holdout if e.severity))},
        "dev_distribution": {"category": dict(Counter(e.category for e in dev if e.category)),
                             "severity": dict(Counter(e.severity for e in dev if e.severity))},
        "weak_distribution": {"category": dict(Counter(e.category for e in weak)),
                              "severity": dict(Counter(e.severity for e in weak))},
    }
    if holdout:
        preds, info = {}, {}
        for variant in ("baseline", "improved"):
            model, info[variant] = train_variant(variant, weak, dev, exclude=holdout, clusters=clusters)
            preds[variant] = predict(model, holdout)
        result["holdout"] = {v: {"training": info[v], **score(holdout, preds[v])} for v in preds}
        # Novelty: how similar is each hold-out NOTAM to the improved model's training texts?
        banned = {_cluster(e, clusters) for e in holdout}
        train_texts = [e for e in list(weak) + dev if _cluster(e, clusters) not in banned]
        sim = novelty(holdout, train_texts)
        novel = [i for i, v in enumerate(sim) if v < 0.6]
        result["holdout_novelty"] = {
            "max_similarity_to_training": {"min": round(min(sim), 3), "median": round(float(np.median(sim)), 3),
                                           "max": round(max(sim), 3)},
            "n_with_similarity_ge_0.8": sum(v >= 0.8 for v in sim),
            "n_novel_lt_0.6": len(novel),
            "novel_subset": {v: score([holdout[i] for i in novel],
                                      {m: [preds[v][m][i] for i in novel] for m in ("ml", "merged")})["merged"]
                             for v in preds} if len(novel) >= 5 else "fewer than 5 novel hold-out NOTAMs",
        }
        result["holdout_bootstrap"] = {
            kind: bootstrap_diff(holdout, preds["baseline"]["merged"], preds["improved"]["merged"], k, kind)
            for kind, k in (("category", 0), ("severity", 1))}
    result["dev_cv"] = dev_cross_validation(weak, dev, repeats=repeats, clusters=clusters)
    result["verdict"] = verdict(result)
    return result


def verdict(result: dict) -> str:
    if "holdout" not in result or not isinstance(result.get("dev_cv"), dict) or "paired_difference" not in result["dev_cv"]:
        return "insufficient data for a verdict"
    parts = []
    for kind in ("category", "severity"):
        h_base = result["holdout"]["baseline"]["merged"][kind]["macro_f1"]
        h_imp = result["holdout"]["improved"]["merged"][kind]["macro_f1"]
        boot = result["holdout_bootstrap"][kind]
        pd = result["dev_cv"]["paired_difference"][kind]
        ci = boot.get("ci95")
        consistent = pd["repeats_improved_better"] == pd["repeats"] and ci and ci[0] > 0
        parts.append(f"{kind}: hold-out macro-F1 {h_base} -> {h_imp}; dev-CV paired diff {pd['mean_diff']:+.4f} "
                     f"(better in {pd['repeats_improved_better']}/{pd['repeats']} repeats); bootstrap 95% CI {ci} "
                     f"=> {'improvement supported' if consistent else 'improvement NOT established'}")
    return " | ".join(parts)
