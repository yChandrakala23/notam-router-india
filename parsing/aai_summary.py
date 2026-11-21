"""Parser for NOTAM blocks extracted from AAI (AIM India) monthly NOTAM summaries.

Owner: Person A.

The AAI monthly summary PDFs list every NOTAM in force on the 1st of the month,
grouped by aerodrome / FIR.  Each record looks like::

    A0100/26 2601180630/2604152359[EST]
    [schedule line(s), e.g. "DLY 0030-0230" or "SR-SS"]
    E-text ...

Important limitations of this source (documented in the report):

* There is **no Q-line**: no Q-code, no FL limits, no centre/radius.  Category
  and severity therefore come from the ML fallback, and geometry is an
  aerodrome-centred default circle when the aerodrome coordinates are known.
* The aerodrome is given by a *section heading* ("KOLKATA VECC").  Because
  ``ingestion/aai.extract_notam_blocks`` splits the PDF text at NOTAM ids, the
  heading of a section lands at the **end of the previous NOTAM's block**.  The
  location therefore has to be tracked statefully in document order.  The very
  first section of each PDF has no preceding block, so its location is unknown.
* PDF page furniture (page footers, running titles) is mixed into the text and
  is removed from the E-text (the raw text is stored unchanged).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from parsing.qline import parse_notam_datetime

INDIAN_ICAO = re.compile(r"^V[AEIO][A-Z]{2}$")

# Region (from the PDF file name) -> issuing NOTAM office and FIR.
REGION_NOF = {
    "delhi": ("VIDP", "VIDF"),
    "mumbai": ("VABB", "VABF"),
    "chennai": ("VOMM", "VOMF"),
    "kolkata": ("VECC", "VECF"),
}

AAI_HEADER = re.compile(
    r"^\s*(?P<id>(?P<series>[A-Z])(?P<number>\d{4})/(?P<year>\d{2}))\s+"
    r"(?P<b>\d{10})\s*/\s*(?P<c>\d{10}|PERM)\s*(?P<est>EST)?",
    re.IGNORECASE,
)

_FURNITURE = [
    re.compile(r"^\s*MONTHLY\s+NOTAM\s+SUMMARY.*$", re.I),
    re.compile(r"^.*NOTAM\s+SUMMARY\s*\([A-Z]-SERIES\).*$", re.I),
    re.compile(r"^.*\bPAGE\s+\d+(\s+OF\s+\d+)?\s*$", re.I),
    re.compile(r"^\s*(PA)?GE\s+\d+\s+OF\s+\d+\s*$", re.I),
]

_SCHEDULE_TOKEN = re.compile(
    r"^(DLY|DAILY|SR|SS|H24|EV|EXC|AND|PLUS\d*|MINUS\d*|TO|"
    r"MON|TUE|WED|THU|FRI|SAT|SUN|"
    r"JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|"
    r"[\d,\-+/:]+|(MON|TUE|WED|THU|FRI|SAT|SUN)-(MON|TUE|WED|THU|FRI|SAT|SUN)|"
    r"SR-SS|SS-SR|SR\w*-SS\w*)$"
)

# Section heading: "<NAME> <ICAO>[/<ICAO>...]".  Name has no digits.
_HEADING = re.compile(
    r"^\s*(?P<name>[A-Z][A-Z .,'&()/-]{0,70}?)\s*"
    r"(?P<codes>V[AEIO][A-Z]{2}(?:\s*/\s*V[AEIO][A-Z]{2})*)\s*/?\s*$"
)
# 4-letter English words that look like Indian ICAO codes.
_NOT_ICAO = {
    "VOID", "VIEW", "VIDE", "VISA", "VOTE", "VEST", "VERY", "VENT", "VEIL",
    "VAIN", "VARY", "VASE", "VAST", "VERB", "VETO", "VICE", "VIAL", "VIOL",
    "VOLT", "VOWS", "VIAS", "VEER", "VERT", "VIZ",
}


@dataclass
class AaiNotam:
    notam_id: Optional[str] = None
    series: Optional[str] = None
    number: Optional[int] = None
    year: Optional[int] = None
    nof: Optional[str] = None
    fir_code: Optional[str] = None
    location: Optional[str] = None            # aerodrome / FIR from heading
    location_name: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_permanent: bool = False
    end_estimated: bool = False
    schedule: Optional[str] = None
    e_text: Optional[str] = None
    next_heading: Optional[tuple[str, str]] = None  # (codes, name) found in tail
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and self.valid_from is not None


def region_from_url(source_url: str | None) -> Optional[str]:
    """'.../Delhi_A_2026_04.pdf' -> 'delhi'."""
    if not source_url:
        return None
    match = re.search(r"/([A-Za-z]+)_[A-Z]_\d{4}_\d{2}\.pdf", source_url)
    return match.group(1).lower() if match else None


def is_furniture(line: str) -> bool:
    return any(p.match(line) for p in _FURNITURE)


def _is_schedule_line(line: str) -> bool:
    tokens = line.replace(",", " , ").split()
    if not tokens or len(line) > 90:
        return False
    return all(_SCHEDULE_TOKEN.match(t.upper()) for t in tokens) and any(
        ch.isdigit() for ch in line
    ) or line.strip().upper() in {"SR-SS", "H24", "SS-SR"} or bool(
        re.match(r"^SS\s+MINUS\d+-SS\s+PLUS\d+$", line.strip().upper())
    )


def _match_heading(line: str) -> Optional[tuple[str, str]]:
    match = _HEADING.match(line.upper())
    if not match:
        return None
    name = match.group("name").strip(" /-,")
    codes = [c.strip() for c in match.group("codes").split("/") if c.strip()]
    if any(c in _NOT_ICAO for c in codes):
        return None
    if len(name.split()) > 8 or any(ch.isdigit() for ch in name):
        return None
    if not name and len(codes) == 1:
        return None
    return "/".join(codes), name


def normalize_for_hash(text: str) -> str:
    """Whitespace-collapsed text without page furniture or headings."""
    lines = []
    for line in text.replace("\r", "").splitlines():
        if not line.strip() or is_furniture(line):
            continue
        lines.append(" ".join(line.split()))
    return "\n".join(lines).upper()


def content_hash(nof: str | None, text: str) -> str:
    """SHA-256 identifying the *content* of a summary block.

    The same NOTAM is repeated in consecutive monthly summaries with different
    page furniture around it; normalising first makes those repeats collapse
    to one raw record (idempotent ingestion).
    """
    body = normalize_for_hash(text)
    # Drop a trailing section heading: it belongs to the next NOTAM.
    lines = body.splitlines()
    while lines and _match_heading(lines[-1]):
        lines.pop()
    payload = f"AAI|{nof or ''}|" + "\n".join(lines)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_block(raw_text: str, *, nof: str | None = None,
                fir_code: str | None = None) -> AaiNotam:
    """Parse one AAI summary block (without location state)."""
    result = AaiNotam(nof=nof, fir_code=fir_code)
    text = (raw_text or "").replace("\r", "")
    lines = [ln for ln in text.splitlines()]
    if not text.strip():
        result.errors.append("empty block")
        return result

    header = AAI_HEADER.match(lines[0]) if lines else None
    if not header:
        header = AAI_HEADER.match(" ".join(text.split()))
    if not header:
        result.errors.append("unrecognised AAI header (id + B/C validity)")
        return result

    result.notam_id = header.group("id").upper()
    result.series = header.group("series").upper()
    result.number = int(header.group("number"))
    result.year = int(header.group("year"))
    try:
        result.valid_from = parse_notam_datetime(header.group("b"))
    except ValueError as exc:
        result.errors.append(f"invalid start of validity: {exc}")
    c_value = header.group("c").upper()
    if c_value == "PERM":
        result.is_permanent = True
    else:
        try:
            result.valid_until = parse_notam_datetime(c_value)
        except ValueError as exc:
            result.errors.append(f"invalid end of validity: {exc}")
        result.end_estimated = bool(header.group("est"))
    if result.valid_from and result.valid_until and result.valid_until < result.valid_from:
        result.errors.append("end of validity precedes start")

    # Body: rest of first line + remaining lines, minus furniture.
    first_rest = lines[0][header.end():] if AAI_HEADER.match(lines[0]) else ""
    body_lines = [first_rest] + lines[1:]
    body_lines = [ln for ln in body_lines if ln.strip() and not is_furniture(ln)]

    # Trailing heading (belongs to the following NOTAMs).  It can be followed
    # by one short city line, e.g. "KEMPEGOWDA INTERNATIONAL AIRPORT VOBL" /
    # "BENGALURU", so look at the last 3 non-empty lines.
    for back in range(1, min(3, len(body_lines)) + 1):
        heading = _match_heading(body_lines[-back])
        if heading:
            tail = body_lines[-back + 1:] if back > 1 else []
            if all(len(t.split()) <= 3 and not any(c.isdigit() for c in t)
                   for t in tail):
                result.next_heading = heading
                body_lines = body_lines[:-back]
            break

    schedule = []
    while body_lines and _is_schedule_line(body_lines[0]):
        schedule.append(" ".join(body_lines.pop(0).split()))
    result.schedule = " ".join(schedule) or None

    e_text = " ".join(" ".join(body_lines).split())
    result.e_text = e_text or None
    if not result.e_text:
        result.warnings.append("empty E-text")
    return result


def parse_summary_records(
    records: Iterable[dict],
) -> list[AaiNotam]:
    """Parse blocks of one or more summary PDFs **in document order**.

    ``records`` are dicts with at least ``raw_text`` and ``source_url`` (the
    JSONL format written by ``ingestion/aai.py``).  Location state is reset
    whenever the source PDF changes.
    """
    results: list[AaiNotam] = []
    current_url = object()
    current_location: Optional[tuple[str, str]] = None

    for record in records:
        url = record.get("source_url")
        if url != current_url:
            current_url = url
            current_location = None
        region = region_from_url(url)
        nof, fir = REGION_NOF.get(region, (None, None))
        parsed = parse_block(record.get("raw_text", ""), nof=nof, fir_code=fir)
        if current_location:
            codes, name = current_location
            parsed.location = codes.split("/")[0]
            parsed.location_name = name or None
        else:
            parsed.warnings.append("location unknown (first section of PDF)")
        if parsed.next_heading:
            current_location = parsed.next_heading
        results.append(parsed)
    return results
