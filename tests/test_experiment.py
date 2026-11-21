"""Leakage-safe evaluation protocol (SYNTHETIC labelled data)."""

import json

from classification.dataset import Example, human_examples
from classification.experiment import (dev_cross_validation, leakage_audit, make_holdout, metrics, run,
                                       train_variant)
from classification.taxonomy import SEVERITIES
from tests.conftest import synthetic_human_rows


def _human(sheet_writer, n=12):
    ex, _ = human_examples(sheet_writer(synthetic_human_rows(n)))
    return ex


def _weak():
    return [Example("SYNTHETIC WEAK TWY Z CLSD", "AERODROME", "ADVISORY", "QMXLC", "autorouter", "VABB|G0001/26"),
            Example("SYNTHETIC WEAK VOR Q U/S", "NAVAID_COMMS", "RESTRICTIVE", "QNVAS", "autorouter", "VABB|G0002/26"),
            Example("SYNTHETIC WEAK RWY 14 CLSD", "RUNWAY", "RESTRICTIVE", "QMRLC", "autorouter", "VABB|G0003/26")]


def test_holdout_disjoint_by_identity_and_template(sheet_writer, tmp_path):
    human = _human(sheet_writer)
    split = make_holdout(human, path=tmp_path / "split.json")
    hold, dev = set(split["holdout_identities"]), set(split["dev_identities"])
    assert hold and dev and not hold & dev and hold | dev == {e.group for e in human}
    t_hold = {e.template for e in human if e.group in hold}
    t_dev = {e.template for e in human if e.group in dev}
    assert not t_hold & t_dev
    sev_hold = {e.severity for e in human if e.group in hold}
    assert sev_hold == set(SEVERITIES)          # every severity class appears in the hold-out


def test_holdout_is_frozen_and_reused(sheet_writer, tmp_path):
    human = _human(sheet_writer)
    p = tmp_path / "split.json"
    a = make_holdout(human, path=p)
    b = make_holdout(human, path=p)
    assert b["reused"] and a["holdout_identities"] == b["holdout_identities"]
    assert json.loads(p.read_text())["seed"] == 13


def test_training_excludes_evaluated_notams(sheet_writer):
    human = _human(sheet_writer)
    test = human[:5]
    weak = _weak() + [Example(test[0].text, test[0].category, test[0].severity, "QMRLC", "aai_matched", test[0].group)]
    _, info = train_variant("improved", weak, human, exclude=test)
    assert info["excluded_for_leakage"] >= 6       # 5 human test rows + the weak copy of test[0]
    _, base = train_variant("baseline", weak, human, exclude=test)
    assert base["by_label_type"] == {"weak_qcode": 3}


def test_leakage_audit_counts_overlap(sheet_writer):
    human = _human(sheet_writer)
    weak = _weak() + [Example(human[0].text, "RUNWAY", "RESTRICTIVE", "QMRLC", "aai_matched", human[0].group)]
    audit = leakage_audit(weak, human)
    assert audit["shared_notam_identities"] == 1 and audit["shared_exact_texts"] == 1


def test_metrics_report_support_identities_and_under_classification():
    m = metrics(["BLOCKING", "ADVISORY", "ADVISORY"], ["ADVISORY", "ADVISORY", "BLOCKING"],
                SEVERITIES, ["a", "b", "b"])
    assert m["n_predictions"] == 3 and m["n_unique_notams"] == 2
    assert m["under_classification_rate"] == round(1 / 3, 4)
    assert m["per_class"]["BLOCKING"]["support"] == 1 and "RESTRICTIVE" in m["classes_absent_from_reference"]


def test_run_is_reproducible_and_compares_on_identical_split(sheet_writer, tmp_path):
    human = _human(sheet_writer)
    r1 = run(_weak(), human, split_path=tmp_path / "s.json", repeats=2)
    r2 = run(_weak(), human, split_path=tmp_path / "s.json", repeats=2)
    assert r1["holdout"]["baseline"]["merged"]["severity"] == r2["holdout"]["baseline"]["merged"]["severity"]
    assert r1["dev_cv"]["summary"] == r2["dev_cv"]["summary"]
    n = r1["holdout_notams"]
    for v in ("baseline", "improved"):
        assert r1["holdout"][v]["merged"]["severity"]["n_unique_notams"] == n
    assert r1["dev_cv"]["repeats"] == 2 and "verdict" in r1


def test_dev_cv_needs_enough_data():
    assert "status" in dev_cross_validation(_weak(), _weak()[:2])


def test_run_without_labels():
    assert "status" in run(_weak(), [])


def _ex(text, group, sev="ADVISORY", cat="AERODROME"):
    return Example(text=text, category=cat, severity=sev, q_code=None, source="aai_annotated",
                   group=group, label_type="human_preliminary")


def test_similarity_clusters_join_near_duplicates_only():
    from classification.experiment import _cluster, similarity_clusters

    a = _ex("DANGER AREA VOD45 ACTIVATED FOR LIVE FIRING GND TO FL250 DAILY 0400-1000", "X|A1/26")
    b = _ex("DANGER AREA VOD45 ACTIVATED FOR LIVE FIRING GND TO FL250 DAILY 0500-1100", "X|A2/26")
    c = _ex("TWY C CLOSED FOR MAINTENANCE WORK DUE TO RESURFACING", "Y|A3/26")
    cl = similarity_clusters([a, b, c])
    assert _cluster(a, cl) == _cluster(b, cl)
    assert _cluster(a, cl) != _cluster(c, cl)


def test_novelty_is_max_similarity_to_training():
    from classification.experiment import novelty

    train = [_ex("RWY 09/27 CLOSED DUE WIP", "T|1")]
    ev = [_ex("RWY 09/27 CLOSED DUE WIP", "E|1"), _ex("VOR DME OUT OF SERVICE", "E|2")]
    sims = novelty(ev, train)
    assert sims[0] > 0.99 and sims[1] < 0.5
    assert novelty(ev, []) == [0.0, 0.0]


def test_training_excludes_near_duplicate_clusters():
    from classification.experiment import similarity_clusters, train_variant

    held = _ex("DANGER AREA VOD45 ACTIVATED FOR LIVE FIRING GND TO FL250 DAILY 0400-1000", "H|1", "RESTRICTIVE", "NAV_WARNING")
    twin = _ex("DANGER AREA VOD45 ACTIVATED FOR LIVE FIRING GND TO FL250 DAILY 0500-1100", "D|1", "RESTRICTIVE", "NAV_WARNING")
    others = [_ex(f"TWY {c} CLOSED FOR MAINTENANCE", f"D|{i+2}") for i, c in enumerate("ABCDEFGH")]
    others += [_ex(f"ILS RWY {i}0 U/S DUE CALIBRATION", f"N|{i}", "RESTRICTIVE", "NAVAID_COMMS") for i in range(1, 9)]
    cl = similarity_clusters([held, twin] + others)
    _, base = train_variant("improved", [], [twin] + others, exclude=[], clusters=cl)
    _, meta = train_variant("improved", [], [twin] + others, exclude=[held], clusters=cl)
    assert meta["n_train"] == base["n_train"] - 1      # only the near-duplicate twin is dropped
    assert meta["excluded_for_leakage"] >= 1
