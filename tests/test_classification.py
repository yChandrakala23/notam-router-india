"""Merged classifier: Q-code rules + ML fallback + keyword guard."""

import pytest

from classification.merged import classify
from classification.ml import NotamTextModel, clean_text, keyword_guard
from classification.rules import classify_qcode


@pytest.mark.parametrize("code,category,severity", [
    ("QRTCA", "AIRSPACE_RESTRICTION", "BLOCKING"),   # methodology table
    ("QRDCA", "AIRSPACE_RESTRICTION", "BLOCKING"),
    ("QRPCA", "AIRSPACE_RESTRICTION", "BLOCKING"),
    ("QFALC", "AERODROME", "BLOCKING"),             # blocking at src/dst
    ("QMRLC", "RUNWAY", "RESTRICTIVE"),
    ("QNVAS", "NAVAID_COMMS", "RESTRICTIVE"),       # VOR unserviceable
    ("QGAAU", "NAVAID_COMMS", "RESTRICTIVE"),       # GNSS not available
    ("QWULW", "NAV_WARNING", "RESTRICTIVE"),        # UAS will take place
    ("QWMLW", "NAV_WARNING", "BLOCKING"),           # rocket launch (SHAR)
    ("QOBCE", "OBSTACLE", "ADVISORY"),
    ("QPICH", "PROCEDURE", "ADVISORY"),
    ("QMXLC", "AERODROME", "ADVISORY"),             # taxiway closed
    ("QRTCD", "AIRSPACE_RESTRICTION", "ADVISORY"),  # deactivated
    ("QRRAK", "AIRSPACE_RESTRICTION", "ADVISORY"),  # resumed normal ops
])
def test_rule_table(code, category, severity):
    result = classify_qcode(code)
    assert (result.category, result.severity, result.ambiguous) == (category, severity, False)


@pytest.mark.parametrize("code", ["QXXXX", "QKKKK", "QMRXX", "QOBXX"])
def test_ambiguous_codes(code):
    assert classify_qcode(code).ambiguous


@pytest.mark.parametrize("code", [None, "", "Q12", "XRTCA", "QRT1A"])
def test_unusable_codes(code):
    assert classify_qcode(code) is None


def test_rules_win_when_unambiguous():
    r = classify("QRTCA", "anything", model=None)
    assert (r.severity, r.method, r.confidence) == ("BLOCKING", "RULES", 1.0)


def test_no_model_defaults_to_restrictive():
    r = classify(None, "SYNTHETIC TWY B CLSD", model=None)
    assert (r.category, r.severity, r.method) == ("OTHER", "RESTRICTIVE", "DEFAULT")


def test_ambiguous_code_keeps_subject_category():
    r = classify("QMRXX", "SYNTHETIC RWY TEXT", model=None)
    assert r.category == "RUNWAY" and r.severity == "RESTRICTIVE"


@pytest.mark.parametrize("text,severity", [
    ("PSLV ROCKET LAUNCH FM SHAR RANGE", "BLOCKING"),
    ("NO FLT IS PERMITTED OVER THE DNG ZONES", "BLOCKING"),
    ("AIRFIELD CLOSURE DUE SKED AIRFIELD MAINT", "BLOCKING"),
    ("UAS OPS WILL TAKE PLACE", "RESTRICTIVE"),
    ("GPS SONDE BALLOON LAUNCH", "RESTRICTIVE"),
])
def test_keyword_guard(text, severity):
    assert keyword_guard(text).severity == severity


def test_guard_only_raises_severity():
    assert keyword_guard("TWY C CLSD FOR MAINT") is None
    r = classify(None, "ROCKET LAUNCH FROM SHAR", model=None)
    assert r.severity == "BLOCKING" and r.method == "KEYWORD_GUARD"


def _toy_model():
    texts = ["TWY A CLSD", "TWY B CLSD FOR MAINT", "APRON STAND 5 NOT AVBL",
             "VOR U/S", "DME U/S", "ILS LOC U/S",
             "CRANE ERECTED", "OBST CRANE", "TEMPO OBST CRANE ERECTED"]
    cats = ["AERODROME"] * 3 + ["NAVAID_COMMS"] * 3 + ["OBSTACLE"] * 3
    sevs = ["ADVISORY"] * 3 + ["RESTRICTIVE"] * 3 + ["ADVISORY"] * 3
    return NotamTextModel().fit(texts, cats, sevs)


def test_ml_fallback_and_low_confidence_default():
    model = _toy_model()
    confident = classify(None, "VOR U/S", model=model, threshold=0.0)
    assert confident.method == "ML" and confident.category == "NAVAID_COMMS"
    low = classify(None, "VOR U/S", model=model, threshold=1.01)
    assert low.method == "ML_LOW_CONF_DEFAULT" and low.severity == "RESTRICTIVE"


def test_model_save_load(tmp_path):
    model = _toy_model()
    path = model.save(tmp_path / "m.joblib")
    loaded = NotamTextModel.load(path)
    assert loaded.predict(["VOR U/S"])[0].category == model.predict(["VOR U/S"])[0].category
    assert NotamTextModel.load(tmp_path / "missing.joblib") is None


def test_clean_text():
    assert clean_text("rwy 09/27  clsd 0300-0400") == "RWY #/# CLSD #-#"
