"""Training data assembly, de-duplication, leakage exclusion, model fit/load."""

import pytest

from classification.dataset import Example, combine_examples, human_examples
from classification.ml import NotamTextModel
from tests.conftest import synthetic_human_rows


def W(text, cat, sev, group, src="autorouter"):
    return Example(text, cat, sev, "QXXXX", src, group, "weak_qcode")


def H(text, cat, sev, group):
    return Example(text, cat, sev, None, "aai_annotated", group, "human_preliminary")


def test_human_examples_from_sheet(sheet_writer):
    ex, rep = human_examples(sheet_writer(synthetic_human_rows(3)))
    assert len(ex) == 15 and {e.label_type for e in ex} == {"human_preliminary"}
    assert {e.source for e in ex} == {"aai_annotated"}


def test_combine_prefers_human_and_records_disagreement():
    weak = [W("TWY A CLSD", "AERODROME", "ADVISORY", "VIDP|A0001/26"),
            W("VOR U/S", "NAVAID_COMMS", "RESTRICTIVE", "VIDP|A0002/26")]
    human = [H("TWY A CLSD DUE WIP", "AERODROME", "RESTRICTIVE", "VIDP|A0001/26")]
    out, rep = combine_examples(weak, human)
    assert [e.group for e in out] == ["VIDP|A0001/26", "VIDP|A0002/26"]
    assert out[0].label_type == "human_preliminary"
    assert rep.dropped_weak_same_identity == 1
    assert rep.weak_human_disagreements == [{"identity": "VIDP|A0001/26", "field": "severity",
                                             "weak": "ADVISORY", "human": "RESTRICTIVE", "q_code": "QXXXX"}]


def test_combine_text_duplicates_and_conflicts():
    weak = [W("VOR U/S", "NAVAID_COMMS", "RESTRICTIVE", "G1"),
            W("vor  u/s", "NAVAID_COMMS", "RESTRICTIVE", "G2"),   # same normalised text, same labels
            W("VOR U/S", "NAVAID_COMMS", "ADVISORY", "G3")]       # same text, different label
    out, rep = combine_examples(weak, [])
    assert rep.text_duplicates_removed == 1 and len(rep.same_text_conflicts) == 1 and len(out) == 2


def test_leakage_exclusion_by_identity_and_template():
    weak = [W("SYNTHETIC RWY 09 CLSD DUE WIP SEGMENT 1", "RUNWAY", "RESTRICTIVE", "X|A0001/26"),
            W("SYNTHETIC RWY 09 CLSD DUE WIP SEGMENT 2 AND MORE", "RUNWAY", "RESTRICTIVE", "X|A0099/26"),
            W("UNRELATED TEXT HERE", "OBSTACLE", "ADVISORY", "X|A0100/26")]
    held = H("SYNTHETIC RWY 09 CLSD DUE WIP SEGMENT 3", "RUNWAY", "RESTRICTIVE", "X|A0001/26")
    out, rep = combine_examples(weak, [], frozenset({held.group}), frozenset({held.template}))
    assert [e.group for e in out] == ["X|A0100/26"] and rep.excluded_for_leakage == 2


def test_independent_fields_and_minority_class():
    texts = ["TWY A CLSD", "TWY B CLSD", "VOR U/S", "DME U/S", "CRANE ERECTED", "ROCKET LAUNCH"]
    cats = ["AERODROME", "AERODROME", "NAVAID_COMMS", None, "OBSTACLE", "NAV_WARNING"]
    sevs = [None, "ADVISORY", "RESTRICTIVE", "RESTRICTIVE", "ADVISORY", "BLOCKING"]   # BLOCKING: 1 example
    model = NotamTextModel().fit(texts, cats, sevs)
    assert model.meta["n_train_category"] == 5 and model.meta["n_train_severity"] == 5
    probs = model.probabilities("ROCKET LAUNCH FROM SHAR")
    assert set(probs["severity"]) == {"ADVISORY", "RESTRICTIVE", "BLOCKING"}
    assert abs(sum(probs["severity"].values()) - 1) < 1e-3


def test_fit_requires_labels():
    with pytest.raises(ValueError):
        NotamTextModel().fit(["A", "B"], [None, None], ["ADVISORY", "ADVISORY"])


def test_model_metadata_round_trip(tmp_path):
    model = NotamTextModel(meta={"label_mode": "weak+human"}).fit(
        ["TWY A CLSD", "VOR U/S"], ["AERODROME", "NAVAID_COMMS"], ["ADVISORY", "RESTRICTIVE"])
    loaded = NotamTextModel.load(model.save(tmp_path / "m.joblib"))
    assert loaded.meta["label_mode"] == "weak+human" and "config" in loaded.meta
    assert loaded.meta["config"]["classifier"].startswith("LogisticRegression")
