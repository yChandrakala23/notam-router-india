"""Convert an autorouter NOTAM JSON record into ICAO text and parse it.

Owner: Person A.

autorouter returns NOTAMs as structured JSON (Q-line components, Garmin
coordinates, Unix timestamps).  To keep **one** parsing code path, the record is
rendered into standard ICAO NOTAM text and then parsed by
``parsing.qline.parse_notam``.  The original JSON is what gets stored in
``raw_notam.raw_text`` (unchanged); the rendered text is derived data.

autorouter data is commercial: keep it local, never commit it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from parsing.qline import ParsedNotam, parse_notam

GARMIN_SCALE = 90 / (1 << 30)
OPEN_ENDED_SENTINEL = 2147483647


def _ts(value: Any) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if value == OPEN_ENDED_SENTINEL:
        return "PERM"
    return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%y%m%d%H%M")


def _coord(lat_raw: Any, lon_raw: Any, radius: Any) -> str:
    if not all(isinstance(v, (int, float)) for v in (lat_raw, lon_raw, radius)):
        return ""
    lat = lat_raw * GARMIN_SCALE
    lon = lon_raw * GARMIN_SCALE
    lat_total = round(abs(lat) * 60)
    lon_total = round(abs(lon) * 60)
    return (
        f"{lat_total // 60:02d}{lat_total % 60:02d}{'N' if lat >= 0 else 'S'}"
        f"{lon_total // 60:03d}{lon_total % 60:02d}{'E' if lon >= 0 else 'W'}"
        f"{int(radius):03d}"
    )


def notam_id_of(record: dict) -> str | None:
    try:
        return f"{record['series']}{int(record['number']):04d}/{int(record['year']) % 100:02d}"
    except (KeyError, TypeError, ValueError):
        return None


def render_icao_text(record: dict) -> str:
    """Render autorouter JSON as ICAO NOTAM text."""
    nid = notam_id_of(record) or "?"
    kind = (record.get("type") or "N").strip().upper()
    header = f"{nid} NOTAM{kind}"
    if kind in ("R", "C") and record.get("referrednumber") is not None:
        ref = {
            "series": record.get("referredseries"),
            "number": record.get("referrednumber"),
            "year": record.get("referredyear"),
        }
        ref_id = notam_id_of(ref)
        if ref_id:
            header += f" {ref_id}"

    code = f"Q{(record.get('code23') or '').strip()}{(record.get('code45') or '').strip()}"
    lower = record.get("lower")
    upper = record.get("upper")
    q = (
        f"Q) {record.get('fir', '')}/{code}/"
        f"{(record.get('traffic') or '').strip()}/"
        f"{(record.get('purpose') or '').strip()}/"
        f"{(record.get('scope') or '').strip()}/"
        f"{int(lower) if isinstance(lower, (int, float)) else 0:03d}/"
        f"{int(upper) if isinstance(upper, (int, float)) else 999:03d}/"
        f"{_coord(record.get('lat'), record.get('lon'), record.get('radius'))}"
    )
    items = record.get("itema") or []
    if isinstance(items, str):
        items = [items]
    start = _ts(record.get("startvalidity")) or ""
    end = _ts(record.get("endvalidity"))
    line_abc = f"A) {' '.join(items)} B) {start}"
    if end:
        line_abc += f" C) {end}"
        if (record.get("estimation") or "").upper() == "EST" and end != "PERM":
            line_abc += " EST"
    parts = [header, q, line_abc]
    if record.get("itemd"):
        parts.append(f"D) {record['itemd']}")
    parts.append(f"E) {record.get('iteme') or ''}")
    if record.get("itemf") or record.get("itemg"):
        parts.append(f"F) {record.get('itemf') or 'SFC'} G) {record.get('itemg') or 'UNL'}")
    return "\n".join(parts)


def parse_autorouter_record(record: dict | str) -> ParsedNotam:
    """Parse an autorouter record (dict or its JSON text)."""
    if isinstance(record, str):
        try:
            record = json.loads(record)
        except json.JSONDecodeError as exc:
            result = ParsedNotam()
            result.errors.append(f"invalid autorouter JSON: {exc}")
            return result
    return parse_notam(render_icao_text(record))


def canonical_json(record: dict) -> str:
    """Stable JSON serialisation used as raw_text (and for the content hash)."""
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
