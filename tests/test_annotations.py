"""Annotation validation and audit (SYNTHETIC sheets)."""

from classification.annotations import severity_review_reasons, to_markdown, validate


def _row(nid, text, cat, sev, notes="checked against AIP", pc="AERODROME", ps="ADVISORY"):
    return {"nof": "VIDP", "notam_id": nid, "location": "VIDP", "e_text": text, "pred_category": pc,
            "pred_severity": ps, "human_category": cat, "human_severity": sev, "notes": notes}


def test_validation_flags(sheet_writer):
    path = sheet_writer([
        _row("A0001/26", "SYNTHETIC TWY A CLSD", "AERODROME", "ADVISORY"),
        _row("A0002/26", "SYNTHETIC RWY 09 CLSD", "", "RESTRICTIVE"),            # missing category
        _row("A0003/26", "SYNTHETIC VOR U/S", "NAVAID", "HIGH"),                   # alias + invalid
        _row("A0004/26", "SYNTHETIC CRANE", "OBSTACLE", "ADVISORY"),
        _row("A0004/26", "SYNTHETIC CRANE", "OBSTACLE", "ADVISORY"),               # duplicate, same
        _row("A0005/26", "SYNTHETIC APRON", "AERODROME", "ADVISORY"),
        _row("A0005/26", "SYNTHETIC APRON", "AERODROME", "RESTRICTIVE"),           # conflicting duplicate
        _row("A0006/26", "SYNTHETIC TWY A CLSD", "AERODROME", "RESTRICTIVE"),      # same text, other label
        _row("A0007/26", "SYNTHETIC RWY 27 CLSD", "RUNWAY", "BLOCKING", notes="ok"),  # questionable + generic
        _row("BAD", "SYNTHETIC", "AERODROME", "ADVISORY"),                         # malformed id
        {"nof": "VIDP", "notam_id": "A0009/26", "e_text": "SYNTHETIC UNLABELLED"},
    ])
    rep = validate(path)
    msgs = [(i.level, i.notam_id, i.field, i.message) for i in rep.issues]
    by_id = {a.notam_id: a for a in rep.annotations}

    assert by_id["A0002/26"].category is None and by_id["A0002/26"].severity == "RESTRICTIVE"
    assert by_id["A0003/26"].category == "NAVAID_COMMS" and by_id["A0003/26"].severity is None
    assert any(l == "warning" and "alias" in m for l, n, f, m in msgs if n == "A0003/26")
    assert any(l == "error" and "not in the taxonomy" in m for l, n, f, m in msgs if n == "A0003/26")
    assert by_id["A0004/26"].rows == [4, 5]
    assert by_id["A0005/26"].severity is None and by_id["A0005/26"].category == "AERODROME"
    assert any("conflicting severity" in m for _, n, _, m in msgs if n == "A0005/26")
    assert any("identical E-text labelled differently" in m for _, n, _, m in msgs if n == "A0006/26")
    assert any(f == "severity_semantics" and "runway closure" in m for _, n, f, m in msgs if n == "A0007/26")
    assert any(f == "notes" for _, n, f, _ in msgs if n == "A0007/26")
    assert any(f == "identity" and l == "error" for l, n, f, _ in msgs if n == "BAD")
    s = rep.summary()
    assert s["rows"] == 11 and s["unique_identities"] == 7
    md = to_markdown(rep)
    assert "BLOCKING annotations" in md and "A0007/26" in md


def test_empty_sheet_reports_no_labels(sheet_writer):
    rep = validate(sheet_writer([{"nof": "VIDP", "notam_id": "A0001/26", "e_text": "X"}]))
    assert rep.summary()["unique_identities"] == 0
    assert "No usable human annotations" in to_markdown(rep)


def test_missing_file(tmp_path):
    assert validate(tmp_path / "nope.csv").rows == 0


def test_severity_review_reasons():
    assert severity_review_reasons("NAV_WARNING", "BLOCKING", "DANGER AREA DEACTIVATED")
    assert severity_review_reasons("AERODROME", "ADVISORY", "AD CLSD FOR OPS")
    assert severity_review_reasons("NAV_WARNING", "BLOCKING", "UAS OPS WI 2NM OF ARP")
    assert not severity_review_reasons("AERODROME", "BLOCKING", "AD CLSD FOR OPS 1000-1200")
