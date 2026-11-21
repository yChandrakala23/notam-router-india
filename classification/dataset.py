"""Weak-labelled training/evaluation data for the text classifier.

Owner: Person A.

Labels are *weak*: they are produced by the Q-code rules (stage 1) on NOTAMs
that do have a Q-code, and the model learns to reproduce them from the E-text
alone.  Sources:

1. autorouter snapshots (``data/autorouter/*.jsonl``) - Q-code + E-text.
   Commercial: the derived dataset is written to a git-ignored file.
2. Real ICAO-text fixtures in ``tests/fixtures/qline`` (ISRO launch NOTAMs).
3. AAI summary records whose identity (NOF + id) matches an autorouter record:
   the AAI E-text gets the autorouter Q-code's label.  ``group`` is the NOTAM
   identity so cross-validation never puts the same NOTAM in train and test.

Hand-corrected labels (``data/labelled/aai_label_sheet.csv``, columns
``human_category`` / ``human_severity``) are read by evaluate.py when filled.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from classification.rules import classify_qcode
from parsing.aai_summary import parse_summary_records
from parsing.autorouter_record import parse_autorouter_record
from parsing.qline import parse_notam

ROOT = Path(__file__).resolve().parent.parent
AUTOROUTER_DIR = ROOT / "data" / "autorouter"
AAI_DIR = ROOT / "data" / "raw"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "qline"
LABEL_SHEET = ROOT / "data" / "labelled" / "aai_label_sheet.csv"


@dataclass
class Example:
    text: str
    category: Optional[str]          # None = no usable label for this field
    severity: Optional[str]
    q_code: Optional[str]
    source: str                      # autorouter | fixture | aai_matched | aai_annotated
    group: str                       # NOTAM identity, e.g. VIDP|A0100/26
    label_type: str = "weak_qcode"   # weak_qcode | human_preliminary

    @property
    def template(self) -> str:
        from classification.annotations import template_key

        return template_key(self.text)


def _load_jsonl(directory: Path, pattern: str) -> list[dict]:
    rows = []
    for path in sorted(directory.glob(pattern)):
        with path.open(encoding="utf-8") as handle:
            rows.extend(json.loads(line) for line in handle if line.strip())
    return rows


def load_aai_records(directory: Path = AAI_DIR):
    blocks = _load_jsonl(directory, "aai_*.jsonl")
    return blocks, parse_summary_records(blocks)


def build_weak_dataset(
    autorouter_dir: Path = AUTOROUTER_DIR,
    aai_dir: Path = AAI_DIR,
    fixture_dir: Path = FIXTURE_DIR,
    include_aai_matches: bool = True,
) -> list[Example]:
    examples: list[Example] = []
    by_identity: dict[str, tuple[str, str, str]] = {}

    for record in _load_jsonl(autorouter_dir, "*_notams.jsonl"):
        parsed = parse_autorouter_record(record)
        if not parsed.qline or not parsed.e_text:
            continue
        rule = classify_qcode(parsed.qline.q_code)
        if rule is None or rule.ambiguous:
            continue
        group = f"{record.get('nof')}|{parsed.notam_id}"
        examples.append(Example(parsed.e_text, rule.category, rule.severity,
                                parsed.qline.q_code, "autorouter", group))
        by_identity[group] = (rule.category, rule.severity, parsed.qline.q_code)

    for path in sorted(fixture_dir.glob("*.txt")):
        parsed = parse_notam(path.read_text(encoding="utf-8"))
        if parsed.qline and parsed.e_text:
            rule = classify_qcode(parsed.qline.q_code)
            if rule and not rule.ambiguous:
                examples.append(Example(parsed.e_text, rule.category, rule.severity,
                                        parsed.qline.q_code, "fixture",
                                        f"FIXTURE|{parsed.notam_id}"))

    if include_aai_matches and by_identity:
        _, parsed_aai = load_aai_records(aai_dir)
        seen: set[str] = set()
        for item in parsed_aai:
            group = f"{item.nof}|{item.notam_id}"
            if group in by_identity and item.e_text and (group, item.e_text) not in seen:
                seen.add((group, item.e_text))
                category, severity, q_code = by_identity[group]
                examples.append(Example(item.e_text, category, severity, q_code,
                                        "aai_matched", group))
    return examples


def unlabelled_aai(aai_dir: Path = AAI_DIR) -> list:
    """Unique AAI NOTAMs (latest observation per identity) for labelling/inference."""
    _, parsed = load_aai_records(aai_dir)
    latest = {}
    for item in parsed:
        if item.ok and item.e_text:
            latest[(item.nof, item.notam_id)] = item
    return list(latest.values())


def read_human_labels(path: Path = LABEL_SHEET) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [r for r in rows if (r.get("human_category") or "").strip()
            or (r.get("human_severity") or "").strip()]


# ---------------------------------------------------------------------------
# Human (preliminary) labels and the combined training set
# ---------------------------------------------------------------------------


def human_examples(path: Path = LABEL_SHEET) -> tuple[list[Example], "AnnotationReport"]:
    """Valid, de-duplicated AAI annotations as Examples (label_type human_preliminary).

    A field that is missing, invalid or conflicting is None for that NOTAM, so
    category and severity can be trained independently.
    """
    from classification.annotations import validate

    report = validate(path)
    out = [Example(a.e_text, a.category, a.severity, None, "aai_annotated", a.identity,
                   "human_preliminary") for a in report.annotations if a.category or a.severity]
    return out, report


@dataclass
class MergeReport:
    weak_in: int = 0
    human_in: int = 0
    dropped_weak_same_identity: int = 0
    weak_human_disagreements: list = field(default_factory=list)
    text_duplicates_removed: int = 0
    same_text_conflicts: list = field(default_factory=list)
    excluded_for_leakage: int = 0


def combine_examples(weak: list[Example], human: list[Example],
                     exclude_groups: frozenset = frozenset(),
                     exclude_templates: frozenset = frozenset()) -> tuple[list[Example], MergeReport]:
    """Merge weak and human examples without conflicting duplicates.

    * Rows whose identity or text template is in ``exclude_*`` are dropped
      (used to keep evaluation hold-outs out of training).
    * Same NOTAM identity in both sets: the human label is kept (it was made
      on the AAI text); disagreements with the weak label are recorded.
    * Same normalised text with the same labels: kept once.
    * Same normalised text with different labels: both kept only if they are
      different NOTAMs; the conflict is recorded (it is reported, not hidden).
    """
    from classification.ml import clean_text

    rep = MergeReport(weak_in=len(weak), human_in=len(human))

    def keep(e: Example) -> bool:
        if e.group in exclude_groups or e.template in exclude_templates:
            rep.excluded_for_leakage += 1
            return False
        return True

    human = [e for e in human if keep(e)]
    weak = [e for e in weak if keep(e)]
    human_by_group = {e.group: e for e in human}
    merged: list[Example] = list(human)
    for e in weak:
        h = human_by_group.get(e.group)
        if h is not None:
            rep.dropped_weak_same_identity += 1
            for kind in ("category", "severity"):
                if getattr(h, kind) and getattr(e, kind) and getattr(h, kind) != getattr(e, kind):
                    rep.weak_human_disagreements.append(
                        {"identity": e.group, "field": kind, "weak": getattr(e, kind),
                         "human": getattr(h, kind), "q_code": e.q_code})
            continue
        merged.append(e)

    seen: dict[str, Example] = {}
    out: list[Example] = []
    for e in merged:
        key = clean_text(e.text)
        prev = seen.get(key)
        if prev is None:
            seen[key] = e
            out.append(e)
        elif (prev.category, prev.severity) == (e.category, e.severity):
            rep.text_duplicates_removed += 1
        else:
            rep.same_text_conflicts.append({"text": key[:120], "a": [prev.group, prev.category, prev.severity],
                                            "b": [e.group, e.category, e.severity]})
            out.append(e)
    return out, rep
