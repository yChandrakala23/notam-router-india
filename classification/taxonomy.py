"""Single source of truth for NOTAM category and severity labels.

Owner: Person A.

Used by the Q-code rules, the ML fallback, training, evaluation, the
annotation validator, the API response schema and the database CHECK
constraint (``notam_event_category_ck`` / ``notam_event_severity_ck`` in
db/migrations/002_notam_pipeline.sql must list exactly these values).

Categories
----------
Eight categories, derived from the ICAO NOTAM-code *subject* groups (Doc 8126).
No category is merged into another.  The AAI annotation sheet happens to use
only six of them (no AIRSPACE_RESTRICTION, no OTHER); that is a property of
the sampled AAI aerodrome NOTAMs, not a different taxonomy.  Evaluation
reports per-class support so absent classes are visible rather than hidden.

Severity (operational meaning for the route conflict check)
----------------------------------------------------------
BLOCKING     The activity/closure makes the airspace or aerodrome unusable
             while active.  A route is rejected ONLY when it also intersects
             the NOTAM area, overlaps its flight-level band and overlaps its
             validity window (routing/conflicts.py).  BLOCKING is therefore a
             property of the NOTAM, not of a route.
RESTRICTIVE  Use is possible with limitations (facility unserviceable,
             runway closed but aerodrome open, UAS / parachuting activity).
             Never rejects a route; produces a warning when overlapping.
ADVISORY     Information only (obstacles, procedure changes, taxiway works).

Alias policy
------------
Labels are normalised (trim, upper case, spaces/hyphens -> underscores).  A
short list of unambiguous synonyms is mapped explicitly; every alias use is
reported by the annotation validator, never applied silently.  Anything else
is rejected as invalid.
"""

from __future__ import annotations

import re
from typing import Optional

CATEGORIES: tuple[str, ...] = (
    "AIRSPACE_RESTRICTION",  # R*  restricted / danger / prohibited / TRA / MOA
    "NAV_WARNING",           # W*  rocket launch, firing, UAS, parachuting, exercises
    "AERODROME",             # F*, L*, MX/MP/MA/MN  aerodrome, taxiway, apron, lighting
    "RUNWAY",                # MR/MT/MD/MS/MW/MU/MK  runway and declared distances
    "NAVAID_COMMS",          # N*, I*, G*, C*  navaids, ILS, GNSS, comms/surveillance
    "OBSTACLE",              # O*  obstacles, obstacle lights
    "PROCEDURE",             # P*, A*, S*  procedures, airspace organisation, ATS
    "OTHER",                 # K*, X*, unknown
)

SEVERITIES: tuple[str, ...] = ("BLOCKING", "RESTRICTIVE", "ADVISORY")
SEVERITY_RANK = {"ADVISORY": 0, "RESTRICTIVE": 1, "BLOCKING": 2}

CATEGORY_ALIASES = {
    "AIRSPACE_RESTRICTIONS": "AIRSPACE_RESTRICTION",
    "RESTRICTED_AIRSPACE": "AIRSPACE_RESTRICTION",
    "NAVIGATION_WARNING": "NAV_WARNING",
    "NAV_WARNINGS": "NAV_WARNING",
    "AIRPORT": "AERODROME",
    "RWY": "RUNWAY",
    "NAVAID": "NAVAID_COMMS",
    "NAVAIDS": "NAVAID_COMMS",
    "OBSTACLES": "OBSTACLE",
    "PROCEDURES": "PROCEDURE",
}
SEVERITY_ALIASES = {"BLOCK": "BLOCKING", "RESTRICTED": "RESTRICTIVE", "ADVISE": "ADVISORY"}


def _norm(value: Optional[str]) -> str:
    return re.sub(r"[\s\-]+", "_", (value or "").strip().upper())


def normalize_label(value: Optional[str], kind: str) -> tuple[Optional[str], Optional[str]]:
    """Return (label, issue).

    ``label`` is the canonical value or None.  ``issue`` is None for an exact
    canonical value, ``"alias:<raw>"`` when an alias was applied, ``"missing"``
    for an empty cell and ``"invalid:<raw>"`` otherwise.
    """
    if kind not in ("category", "severity"):
        raise ValueError(kind)
    canonical = CATEGORIES if kind == "category" else SEVERITIES
    aliases = CATEGORY_ALIASES if kind == "category" else SEVERITY_ALIASES
    norm = _norm(value)
    if not norm:
        return None, "missing"
    if norm in canonical:
        return norm, None if (value or "").strip() == norm else f"normalised:{value!r}"
    if norm in aliases:
        return aliases[norm], f"alias:{value!r}->{aliases[norm]}"
    return None, f"invalid:{value!r}"


def is_under_classified(true: str, pred: str) -> bool:
    """Predicted severity is less severe than the reference (unsafe direction)."""
    return SEVERITY_RANK[pred] < SEVERITY_RANK[true]
