"""Validation and quality audit of the AAI annotation sheet.

Owner: Person A.

    python -m classification.annotations          # writes evaluation/results/annotation_audit.{md,json}

The human labels in data/labelled/aai_label_sheet.csv are treated as
**preliminary**: they are validated, de-duplicated and audited, but never
changed automatically.  The audit explains *why* a row deserves a second look;
the decision stays with the annotator.

Checks
------
errors   (row field not usable for training/evaluation)
  * missing / invalid category or severity (taxonomy.normalize_label)
  * missing or malformed NOTAM identity (nof + notam_id), empty E-text
  * the same NOTAM identity labelled differently in two rows (conflict)
warnings (usable, but reported)
  * alias or case normalisation applied to a label
  * duplicate identity with identical labels (later rows ignored)
review   (label is valid but questionable; heuristics explained below)
  * identical normalised E-text labelled differently under two identities
  * severity that departs from the definitions in classification/rules.py
    (e.g. runway closure labelled BLOCKING, aerodrome closure labelled
    ADVISORY, "deactivated"/"cancelled" activity labelled BLOCKING)
  * generic or uninformative notes on rows whose label disagrees with the
    system prediction
  * prediction / annotation disagreement (listed, not judged)

The text cues below are used ONLY to raise review flags.  They never set a
label and are not used by the classifier.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from classification.ml import clean_text
from classification.taxonomy import CATEGORIES, SEVERITIES, normalize_label

ROOT = Path(__file__).resolve().parent.parent
LABEL_SHEET = ROOT / "data" / "labelled" / "aai_label_sheet.csv"
RESULTS = ROOT / "evaluation" / "results"
NOTAM_ID = re.compile(r"^[A-Z]\d{4}/\d{2}$")

GENERIC_NOTES = {"", "ok", "okay", "same", "na", "n/a", "-", "--", "none", "checked", "done",
                 "correct", "fine", "yes", "no", "?", "x", "good", "agree", "as predicted"}


def template_key(text: str, n_tokens: int = 6) -> str:
    """Near-duplicate key: first tokens of the cleaned E-text."""
    return " ".join(clean_text(text).split()[:n_tokens])


# ---------------------------------------------------------------------------
# Review cues (audit only)
# ---------------------------------------------------------------------------
_CUES = {
    "aerodrome_closed": r"\b(?:AD|AERODROME|AIRPORT|AIRFIELD)\s+(?:IS\s+)?(?:CLSD|CLOSED)\b|\bAIRFIELD CLOSURE\b|\bAD CLOSURE\b",
    "runway_closed": r"\bRWY\b.*\b(?:CLSD|CLOSED)\b",
    "taxiway_apron": r"\bTWY\b|\bTAXIWAY\b|\bAPRON\b|\bSTAND\b|\bPRKG\b|\bPARKING\b",
    "navaid_us": r"\b(?:VOR|DME|NDB|ILS|LOC|GP|GLIDE PATH|TACAN|RADAR|SSR)\b.*\b(?:U/S|UNSERVICEABLE|NOT AVBL|WITHDRAWN)\b",
    "obstacle": r"\bOBST\b|\bOBSTACLE\b|\bCRANE\b|\bTOWER\b|\bMAST\b",
    "deactivated": r"\bDEACTIVATED\b|\bCANCELLED\b|\bCNL\b|\bWILL NOT TAKE PLACE\b|\bNOT ACT(?:IVE)?\b",
    "launch_firing": r"\bROCKET\b|\bMISSILE\b|\bLIVE FIRING\b|\bFIRING\b|\bFRNG\b",
    "no_flight": (r"\bNO FLT (?:IS )?PERMITTED\b|\bPROHIBITED\b|\bDNG ZONE\b|\bDANGER ZONE\b|\bDNG AREA\b|"
                  r"\bNO ACFT PERMITTED TO OVERFLY\b|\bNO OVER ?FLY\b"),
    # Indian designated areas: V + A/E/I/O + D(anger)/P(rohibited)/R(estricted) + number, e.g. VED-50, VID 129
    "designated_area": r"\bV[AEIO][DPR][- ]?\d{1,3}[A-Z]?\b",
    "airspace_not_available": r"\bAIRSPACE\b.*\bNOT AVBL\b|\bATS RTE\b.*\bNOT AVBL\b",
    "airspace_use_plan": r"\bAIRSPACE USE PLAN\b|\bAUP\b.*\bTSA\b",
    "light_activity": r"\bUAS\b|\bRPAS\b|\bDRONE|\bPARA ?(?:CHUTE|JUMP|GLID)|\bPJE\b|\bBALLOON\b|\bAEROBATIC|\bKITE\b",
    "vertical_limits": r"\b(?:SFC|GND|FL ?\d{2,3}|\d{3,5} ?FT)\b",
    "lateral_limits": r"\b\d{4,6}[NS] ?\d{5,7}[EW]\b|\bRADIUS\b|\bNM\b|\bAREA BOUNDED\b",
}
_CUES_RE = {k: re.compile(v) for k, v in _CUES.items()}


def text_cues(text: str) -> set[str]:
    t = " ".join((text or "").upper().split())
    return {k for k, r in _CUES_RE.items() if r.search(t)}


def severity_review_reasons(category: Optional[str], severity: Optional[str], text: str) -> list[str]:
    """Why a (valid) label may contradict the severity definitions in rules.py."""
    cues = text_cues(text)
    reasons = []
    if severity == "BLOCKING":
        if "deactivated" in cues:
            reasons.append("BLOCKING but the text mentions deactivation/cancellation; rules.py maps "
                           "deactivated/cancelled conditions (CD, CN, AK, HQ) to ADVISORY")
        if category == "RUNWAY" or ("runway_closed" in cues and "aerodrome_closed" not in cues):
            reasons.append("BLOCKING for a runway closure; rules.py treats runway closure (MR..LC) as "
                           "RESTRICTIVE unless the aerodrome itself is closed")
        if category in ("NAVAID_COMMS", "OBSTACLE", "PROCEDURE"):
            reasons.append(f"BLOCKING for category {category}; rules.py gives these at most RESTRICTIVE")
        if category == "AERODROME" and "aerodrome_closed" not in cues:
            reasons.append("BLOCKING AERODROME without aerodrome-closure wording; rules.py reserves "
                           "BLOCKING for FA..LC (aerodrome closed); partial facility limits are RESTRICTIVE/ADVISORY")
        if "light_activity" in cues and not cues & {"launch_firing", "no_flight"}:
            reasons.append("BLOCKING for UAS/parachuting/balloon-type activity; rules.py treats these "
                           "warnings (WU, WP, WL...) as RESTRICTIVE")
        if "airspace_use_plan" in cues:
            reasons.append("BLOCKING for an Airspace Use Plan: it lists many TRA/TSA activations and conditional "
                           "routes, each with its own times and FL band; whether a route is blocked depends on "
                           "which area it crosses, so a single BLOCKING label over-generalises")
        elif category == "NAV_WARNING" and not cues & {"launch_firing", "no_flight", "airspace_not_available"} \
                and "light_activity" not in cues:
            reasons.append("BLOCKING NAV_WARNING without firing/launch/no-flight/airspace-not-available wording; "
                           "rules.py blocks only WM/WD/WW/WR-type hazards and active R* areas")
        if "lateral_limits" not in cues and category in ("NAV_WARNING", "AIRSPACE_RESTRICTION"):
            reasons.append("no lateral limits in the E-text and AAI summaries carry no Q-line circle: "
                           "routing can apply this only at aerodrome / FIR level")
    else:
        if "aerodrome_closed" in cues and "deactivated" not in cues:
            reasons.append(f"{severity} but the text says the aerodrome is closed; rules.py maps aerodrome "
                           "closure (FA..LC) to BLOCKING")
        if cues & {"launch_firing", "no_flight"} and "deactivated" not in cues and severity == "ADVISORY":
            reasons.append("ADVISORY but the text describes firing/launch or a no-flight zone; rules.py "
                           "treats active hazards of this kind as BLOCKING (WM/R*) or at least RESTRICTIVE")
        if "designated_area" in cues and "deactivated" not in cues and severity == "ADVISORY":
            reasons.append("ADVISORY for an activated designated danger/prohibited/restricted area (V?D/V?P/V?R); "
                           "rules.py maps active R* areas to BLOCKING")
        if category == "AERODROME" and cues & {"launch_firing", "no_flight", "designated_area"}:
            reasons.append("category AERODROME for an airspace activity (firing / danger area / no-overfly); "
                           "by Q-code subject this is NAV_WARNING (W*) or AIRSPACE_RESTRICTION (R*)")
        if severity == "ADVISORY" and "runway_closed" in cues and "deactivated" not in cues:
            reasons.append("ADVISORY for a runway closure; rules.py maps runway closure to RESTRICTIVE")
        if severity == "ADVISORY" and "navaid_us" in cues:
            reasons.append("ADVISORY for an unserviceable navaid; rules.py maps navaid unserviceable to RESTRICTIVE")
    return reasons


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    row: int                 # 1-based data row (header = row 0)
    nof: str
    notam_id: str
    level: str               # error | warning | review
    field: str
    message: str


@dataclass
class Annotation:
    nof: str
    notam_id: str
    location: str
    e_text: str
    category: Optional[str]          # None when missing/invalid/conflicting
    severity: Optional[str]
    notes: str
    pred_category: str
    pred_severity: str
    rows: list[int] = field(default_factory=list)
    label_type: str = "human_preliminary"

    @property
    def identity(self) -> str:
        return f"{self.nof}|{self.notam_id}"

    @property
    def template(self) -> str:
        return template_key(self.e_text)


@dataclass
class AnnotationReport:
    path: str
    rows: int
    annotations: list[Annotation]
    issues: list[Issue]

    def usable(self, field_name: str) -> list[Annotation]:
        return [a for a in self.annotations if getattr(a, field_name) is not None]

    def summary(self) -> dict:
        lv = Counter(i.level for i in self.issues)
        return {
            "rows": self.rows,
            "unique_identities": len(self.annotations),
            "usable_category": len(self.usable("category")),
            "usable_severity": len(self.usable("severity")),
            "usable_both": sum(1 for a in self.annotations if a.category and a.severity),
            "issues_by_level": dict(lv),
            "category_distribution": dict(Counter(a.category for a in self.usable("category"))),
            "severity_distribution": dict(Counter(a.severity for a in self.usable("severity"))),
        }


def load_rows(path: Path = LABEL_SHEET) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def validate(path: Path = LABEL_SHEET) -> AnnotationReport:
    rows = load_rows(path)
    issues: list[Issue] = []
    by_identity: dict[str, Annotation] = {}
    conflicted: set[tuple[str, str]] = set()
    labelled_rows = 0

    for idx, row in enumerate(rows, start=1):
        nof = (row.get("nof") or "").strip()
        nid = (row.get("notam_id") or "").strip().upper()
        text = (row.get("e_text") or "").strip()
        raw_cat, raw_sev = row.get("human_category"), row.get("human_severity")
        if not (raw_cat or "").strip() and not (raw_sev or "").strip():
            issues.append(Issue(idx, nof, nid, "error", "labels", "row not annotated (both labels empty)"))
            continue
        labelled_rows += 1
        if not nof or not NOTAM_ID.match(nid):
            issues.append(Issue(idx, nof, nid, "error", "identity",
                                f"missing/malformed NOTAM identity (nof={nof!r}, notam_id={nid!r}); row cannot be grouped"))
            continue
        if not text:
            issues.append(Issue(idx, nof, nid, "error", "e_text", "empty E-text"))
            continue

        labels = {}
        for kind, raw in (("category", raw_cat), ("severity", raw_sev)):
            label, issue = normalize_label(raw, kind)
            labels[kind] = label
            if issue == "missing":
                issues.append(Issue(idx, nof, nid, "error", kind, f"human_{kind} missing"))
            elif issue and issue.startswith("invalid"):
                allowed = ", ".join(CATEGORIES if kind == "category" else SEVERITIES)
                issues.append(Issue(idx, nof, nid, "error", kind,
                                    f"human_{kind} {issue.split(':', 1)[1]} is not in the taxonomy ({allowed})"))
            elif issue:
                issues.append(Issue(idx, nof, nid, "warning", kind, f"label {issue}"))

        ann = Annotation(nof, nid, (row.get("location") or "").strip(), text,
                         labels["category"], labels["severity"], (row.get("notes") or "").strip(),
                         (row.get("pred_category") or "").strip(), (row.get("pred_severity") or "").strip(),
                         [idx])
        key = ann.identity
        if key in by_identity:
            first = by_identity[key]
            first.rows.append(idx)
            for kind in ("category", "severity"):
                a, b = getattr(first, kind), getattr(ann, kind)
                if (key, kind) in conflicted:
                    continue
                if a and b and a != b:
                    issues.append(Issue(idx, nof, nid, "error", kind,
                                        f"conflicting {kind} for the same NOTAM: rows {first.rows[0]} -> {a}, "
                                        f"{idx} -> {b}; {kind} excluded for this NOTAM until resolved"))
                    conflicted.add((key, kind))
                    setattr(first, kind, None)
                elif b and not a:
                    setattr(first, kind, b)
            issues.append(Issue(idx, nof, nid, "warning", "identity",
                                f"duplicate NOTAM identity (also row {first.rows[0]}); one example kept"))
            continue
        by_identity[key] = ann

    annotations = list(by_identity.values())

    # identical text, different identity, different labels
    by_text = defaultdict(list)
    for a in annotations:
        by_text[clean_text(a.e_text)].append(a)
    for group in by_text.values():
        if len(group) < 2:
            continue
        for kind in ("category", "severity"):
            values = {getattr(a, kind) for a in group if getattr(a, kind)}
            if len(values) > 1:
                ids = ", ".join(f"{a.identity}={getattr(a, kind)}" for a in group)
                for a in group:
                    issues.append(Issue(a.rows[0], a.nof, a.notam_id, "review", kind,
                                        f"identical E-text labelled differently across NOTAMs: {ids}"))

    note_counts = Counter(a.notes.lower() for a in annotations if a.notes)
    for a in annotations:
        disagree = (a.category and a.pred_category and a.category != a.pred_category) or \
                   (a.severity and a.pred_severity and a.severity != a.pred_severity)
        note = a.notes.lower()
        generic = note in GENERIC_NOTES or len(note) < 5 or (note_counts[note] >= 10 and note)
        if disagree and generic:
            issues.append(Issue(a.rows[0], a.nof, a.notam_id, "review", "notes",
                                f"label differs from prediction but the note is generic/uninformative ({a.notes!r}); "
                                "record the reason for the decision"))
        if a.category and a.pred_category and a.category != a.pred_category:
            issues.append(Issue(a.rows[0], a.nof, a.notam_id, "review", "category",
                                f"annotated {a.category}, predicted {a.pred_category}"))
        if a.severity and a.pred_severity and a.severity != a.pred_severity:
            issues.append(Issue(a.rows[0], a.nof, a.notam_id, "review", "severity",
                                f"annotated {a.severity}, predicted {a.pred_severity}"))
        for reason in severity_review_reasons(a.category, a.severity, a.e_text):
            issues.append(Issue(a.rows[0], a.nof, a.notam_id, "review", "severity_semantics", reason))

    report = AnnotationReport(str(path), len(rows), annotations, issues)
    report.labelled_rows = labelled_rows  # type: ignore[attr-defined]
    return report


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def to_markdown(report: AnnotationReport) -> str:
    s = report.summary()
    lines = ["# Annotation audit — data/labelled/aai_label_sheet.csv (generated)", "",
             f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "",
             "Labels are **preliminary**: nothing below changes a label. Review flags are heuristics "
             "that compare the label with the severity definitions in `classification/rules.py`; "
             "each flag states its reason.", "",
             f"- rows in sheet: {s['rows']}",
             f"- rows with at least one human label: {getattr(report, 'labelled_rows', 'n/a')}",
             f"- unique NOTAM identities with labels: {s['unique_identities']}",
             f"- usable for category / severity / both: {s['usable_category']} / {s['usable_severity']} / {s['usable_both']}",
             f"- issues by level: {s['issues_by_level']}",
             f"- category distribution: {s['category_distribution']}",
             f"- severity distribution: {s['severity_distribution']}", ""]
    if s["unique_identities"] == 0:
        lines += ["**No usable human annotations.** Fill `human_category` and `human_severity` "
                  "(and `notes`) in the sheet, then re-run `python -m classification.annotations`.", ""]

    errors = [i for i in report.issues if i.level == "error" and i.message != "row not annotated (both labels empty)"]
    unannotated = sum(1 for i in report.issues if i.message == "row not annotated (both labels empty)")
    lines += ["## Errors (excluded from training/evaluation)", "",
              f"Unannotated rows: {unannotated}", ""]
    if errors:
        lines += ["| row | NOTAM | field | problem |", "|---|---|---|---|"]
        lines += [f"| {i.row} | {i.nof} {i.notam_id} | {i.field} | {i.message} |" for i in errors]
    else:
        lines.append("None.")

    lines += ["", "## BLOCKING annotations (each needs explicit confirmation)", ""]
    blocking = [a for a in report.annotations if a.severity == "BLOCKING"]
    if not blocking:
        lines.append("No rows are annotated BLOCKING.")
    for a in blocking:
        reasons = severity_review_reasons(a.category, a.severity, a.e_text)
        cues = sorted(text_cues(a.e_text))
        lines += [f"### row {a.rows[0]} — {a.nof} {a.notam_id} ({a.location or 'location unknown'})", "",
                  f"- label: {a.category} / **BLOCKING**; predicted {a.pred_category} / {a.pred_severity}",
                  f"- note: {a.notes or '(none)'}",
                  f"- text cues found: {', '.join(cues) or 'none'}",
                  f"- E-text: {a.e_text[:400]}", ""]
        if reasons:
            lines += ["Needs review because:"] + [f"- {r}" for r in reasons]
        else:
            lines.append("No automatic concern found. Still unverified: confirm that the activity makes the "
                         "airspace/aerodrome unusable while active (not merely restricted).")
        lines.append("")

    sem = [i for i in report.issues if i.field == "severity_semantics" and
           not any(a.severity == "BLOCKING" and a.notam_id == i.notam_id and a.nof == i.nof for a in blocking)]
    lines += ["## Other questionable severity assignments", ""]
    if sem:
        lines += ["| row | NOTAM | reason |", "|---|---|---|"]
        lines += [f"| {i.row} | {i.nof} {i.notam_id} | {i.message} |" for i in sem]
    else:
        lines.append("None flagged.")

    for title, flt in (("Conflicts across identical texts", lambda i: "identical E-text" in i.message),
                       ("Generic notes on disputed rows", lambda i: i.field == "notes"),
                       ("Warnings (aliases, normalisation, duplicates)", lambda i: i.level == "warning")):
        sel = [i for i in report.issues if flt(i)]
        lines += ["", f"## {title}", ""]
        if sel:
            lines += ["| row | NOTAM | field | detail |", "|---|---|---|---|"]
            lines += [f"| {i.row} | {i.nof} {i.notam_id} | {i.field} | {i.message} |" for i in sel]
        else:
            lines.append("None.")

    cat_dis = [i for i in report.issues if i.field == "category" and i.level == "review"
               and i.message.startswith("annotated")]
    sev_dis = [i for i in report.issues if i.field == "severity" and i.level == "review"
               and i.message.startswith("annotated")]
    lines += ["", "## Prediction vs annotation disagreements", "",
              f"Category: {len(cat_dis)} rows; severity: {len(sev_dis)} rows "
              "(full list in annotation_audit.json). Disagreement is not evidence that the label is wrong.", ""]
    pairs = Counter(i.message for i in sev_dis)
    if pairs:
        lines += ["| severity pair | rows |", "|---|---|"] + [f"| {k} | {v} |" for k, v in pairs.most_common()]
    return "\n".join(lines)


def main(argv=None) -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Validate and audit the AAI annotation sheet")
    parser.add_argument("--sheet", default=str(LABEL_SHEET))
    args = parser.parse_args(argv)
    report = validate(Path(args.sheet))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "annotation_audit.md").write_text(to_markdown(report), encoding="utf-8")
    (RESULTS / "annotation_audit.json").write_text(json.dumps({
        "summary": report.summary(),
        "issues": [asdict(i) for i in report.issues if i.message != "row not annotated (both labels empty)"],
        "unannotated_rows": sum(1 for i in report.issues if i.message == "row not annotated (both labels empty)"),
    }, indent=1), encoding="utf-8")
    print(json.dumps(report.summary(), indent=1))
    print(f"Wrote {RESULTS / 'annotation_audit.md'}")


if __name__ == "__main__":
    main()
