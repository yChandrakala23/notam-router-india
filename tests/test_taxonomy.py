"""Label taxonomy is shared by rules, ML, evaluation, API and the DB CHECK constraints."""

import re
from pathlib import Path

import pytest

from classification import rules
from classification.taxonomy import CATEGORIES, SEVERITIES, is_under_classified, normalize_label


@pytest.mark.parametrize("raw,expected,issue_prefix", [
    ("AERODROME", "AERODROME", None),
    (" aerodrome ", "AERODROME", "normalised"),
    ("nav-warning", "NAV_WARNING", "normalised"),
    ("Navaid", "NAVAID_COMMS", "alias"),
    ("AIRSPACE RESTRICTIONS", "AIRSPACE_RESTRICTION", "alias"),
    ("", None, "missing"),
    ("CLOSURE", None, "invalid"),
])
def test_normalize_category(raw, expected, issue_prefix):
    label, issue = normalize_label(raw, "category")
    assert label == expected
    assert (issue is None) if issue_prefix is None else issue.startswith(issue_prefix)


def test_normalize_severity():
    assert normalize_label("blocking", "severity")[0] == "BLOCKING"
    assert normalize_label("HIGH", "severity") == (None, "invalid:'HIGH'")


def test_rules_reexport_same_objects():
    assert rules.CATEGORIES is CATEGORIES and rules.SEVERITIES is SEVERITIES


def test_db_check_constraints_match_taxonomy():
    sql = Path("db/migrations/002_notam_pipeline.sql").read_text(encoding="utf-8")
    cat = re.search(r"category IN \((.*?)\)\)", sql, re.S).group(1)
    sev = re.search(r"severity IN \((.*?)\)\)", sql, re.S).group(1)
    assert set(re.findall(r"'([A-Z_]+)'", cat)) == set(CATEGORIES)
    assert set(re.findall(r"'([A-Z_]+)'", sev)) == set(SEVERITIES)


def test_under_classification():
    assert is_under_classified("BLOCKING", "RESTRICTIVE") and not is_under_classified("ADVISORY", "BLOCKING")
