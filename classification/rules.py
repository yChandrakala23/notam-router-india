"""Stage 1 of the merged classifier: deterministic Q-code rules.

Owner: Person A.

A Q-code is ``Q`` + 2-letter *subject* + 2-letter *condition* (ICAO Doc 8126,
NOTAM Code; decode tables also in ICAO Doc 8400).  Subject/condition meanings
used below were checked against the FAA's published ICAO NOTAM code tables
(FAA JO 7930.2, "ICAO Q-codes" appendix:
https://www.faa.gov/air_traffic/publications/atpubs/ntm/notapda.html),
e.g. CA activated, CD deactivated, CN cancelled, AK resumed normal operations,
AS unserviceable, LC closed, LW will take place, HV work completed,
RT temporary restricted area, WM missile/gun/rocket firing, WU unmanned aircraft.  Example: ``QRTCA`` =
subject RT (temporary restricted area) + condition CA (activated).

Severity levels used by the conflict check (Person B):

* BLOCKING     - route must not cross while active (FL overlap)
* RESTRICTIVE  - keep route, attach warning
* ADVISORY     - information only

The table is a research simplification (methodology v2 section 5 layer 3), written
conservatively.  It is not exhaustive: unknown subjects fall back to the
first-letter group, and Q-codes that cannot be decided (QXXXX, QKKKK, a
condition of XX for subjects where the condition decides severity) are marked
``ambiguous`` so the ML stage may look at the E-text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Labels live in classification/taxonomy.py (shared with training, evaluation,
# the API and the DB CHECK constraints).  Re-exported here for compatibility.
from classification.taxonomy import CATEGORIES, SEVERITIES, SEVERITY_RANK  # noqa: E402,F401

# Conditions meaning the hazard is gone / back to normal.
_INACTIVE_CONDITIONS = {"CD", "CN", "AK", "AX", "HV", "CC", "AO", "HQ"}
# Conditions meaning a facility is unusable.
_UNSERVICEABLE = {"AS", "AU", "AW", "LC", "LD", "CT", "AC"}
_LIMITED = {"LT", "LI", "LN", "LV", "LH", "AP", "AH", "LS", "LP", "AM", "AN", "AD", "AR"}

# Warnings considered hazardous enough to block (methodology: rocket launches
# from SHAR, firing ranges, explosives, volcanic ash, radioactive release).
_BLOCKING_WARNINGS = {"WM", "WD", "WW", "WR"}

_RUNWAY_SUBJECTS = {"MR", "MT", "MD", "MS", "MW", "MU", "MK", "MG", "MO"}


@dataclass(frozen=True)
class RuleResult:
    category: str
    severity: str
    ambiguous: bool       # True -> ML stage may override severity / category
    reason: str           # human-readable rule that fired
    confidence: float = 1.0


def _category(subject: str) -> str:
    first = subject[:1]
    if first == "R":
        return "AIRSPACE_RESTRICTION"
    if first == "W":
        return "NAV_WARNING"
    if subject in _RUNWAY_SUBJECTS:
        return "RUNWAY"
    if first in ("M", "F", "L"):
        return "AERODROME"
    if first in ("N", "I", "G", "C"):
        return "NAVAID_COMMS"
    if first == "O":
        return "OBSTACLE"
    if first in ("P", "A", "S"):
        return "PROCEDURE"
    return "OTHER"


def classify_qcode(q_code: Optional[str]) -> Optional[RuleResult]:
    """Map a Q-code to category + severity.  None when the code is unusable."""
    if not q_code:
        return None
    code = q_code.strip().upper()
    if len(code) != 5 or not code.startswith("Q") or not code[1:].isalpha():
        return None

    subject, condition = code[1:3], code[3:5]
    first = subject[0]

    if subject in ("XX", "KK") or first in ("X", "K"):
        return RuleResult("OTHER", "ADVISORY", True,
                          f"{code}: subject {subject} carries no meaning (plain language / checklist)")

    category = _category(subject)

    if condition in _INACTIVE_CONDITIONS:
        return RuleResult(category, "ADVISORY", False,
                          f"{code}: condition {condition} = deactivated/normal")

    if first == "R":
        return RuleResult(category, "BLOCKING", False,
                          f"{code}: airspace restriction ({subject}) active")

    if first == "W":
        if subject in _BLOCKING_WARNINGS:
            return RuleResult(category, "BLOCKING", False,
                              f"{code}: hazardous activity ({subject})")
        return RuleResult(category, "RESTRICTIVE", condition == "XX",
                          f"{code}: navigation warning ({subject})")

    if subject == "FA":  # aerodrome as a whole
        if condition == "LC":
            return RuleResult("AERODROME", "BLOCKING", False,
                              f"{code}: aerodrome closed (blocking at source/destination)")
        if condition in _LIMITED or condition in _UNSERVICEABLE:
            return RuleResult("AERODROME", "RESTRICTIVE", False,
                              f"{code}: aerodrome operations limited")
        return RuleResult("AERODROME", "ADVISORY", condition == "XX",
                          f"{code}: aerodrome information")

    if category == "RUNWAY":
        if condition == "LC":
            return RuleResult(category, "RESTRICTIVE", False, f"{code}: runway closed")
        return RuleResult(category, "ADVISORY", condition == "XX", f"{code}: runway information")

    if subject == "AR":  # ATS route
        if condition in _UNSERVICEABLE:
            return RuleResult("PROCEDURE", "RESTRICTIVE", False, f"{code}: ATS route closed/unavailable")
        return RuleResult("PROCEDURE", "ADVISORY", condition == "XX", f"{code}: ATS route information")

    if category == "NAVAID_COMMS":
        if condition in _UNSERVICEABLE or condition in {"LS", "LF", "LG", "LA"}:
            return RuleResult(category, "RESTRICTIVE", False, f"{code}: navaid/comms unserviceable")
        return RuleResult(category, "ADVISORY", condition == "XX", f"{code}: navaid/comms information")

    if first == "S":  # ATS services
        if condition in _UNSERVICEABLE:
            return RuleResult(category, "RESTRICTIVE", False, f"{code}: ATS unit unserviceable")
        return RuleResult(category, "ADVISORY", condition == "XX", f"{code}: ATS information")

    if first == "P":
        if condition in {"AU", "LC"}:
            return RuleResult(category, "RESTRICTIVE", False, f"{code}: procedure not available")
        return RuleResult(category, "ADVISORY", condition == "XX", f"{code}: procedure change")

    # O*, L*, M* (taxiway/apron), F* (other facilities), A* (other airspace org.)
    return RuleResult(category, "ADVISORY", condition == "XX", f"{code}: {category.lower()} information")


def more_severe(a: str, b: str) -> str:
    return a if SEVERITY_RANK[a] >= SEVERITY_RANK[b] else b
