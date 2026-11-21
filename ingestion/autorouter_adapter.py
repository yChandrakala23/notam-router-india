
"""Normalize Autorouter NOTAM records for the project.

Research use only. Keep raw commercial NOTAM data private.
Do not treat replacement records as active without resolving
their references and validity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


GARMIN_SCALE = 90 / (1 << 30)
OPEN_ENDED_SENTINEL = 2147483647


def decode_coordinate(value: Any) -> float | None:
    """Convert an Autorouter Garmin coordinate to decimal degrees."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None

    return value * GARMIN_SCALE


def timestamp_to_utc(value: Any) -> str | None:
    """Convert a Unix timestamp to an ISO-8601 UTC string."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None

    if value == OPEN_ENDED_SENTINEL:
        return None

    return datetime.fromtimestamp(
        value, tz=timezone.utc
    ).isoformat()


def normalize_notam(record: dict[str, Any]) -> dict[str, Any]:
    """Map an Autorouter record to a normalized project record.

    This preserves source identifiers and separates the Q-code
    components. It does not decide whether the NOTAM is active.
    """
    end_raw = record.get("endvalidity")
    end_open_ended = end_raw == OPEN_ENDED_SENTINEL

    code23 = (record.get("code23") or "").strip()
    code45 = (record.get("code45") or "").strip()

    return {
        # Source provenance
        "source": "autorouter",
        "source_id": record.get("id"),
        "notam_type": record.get("type"),
        "series": record.get("series"),
        "number": record.get("number"),
        "year": record.get("year"),

        # Replacement references: resolve before determining activity
        "referred_series": record.get("referredseries"),
        "referred_number": record.get("referrednumber"),
        "referred_year": record.get("referredyear"),

        # Q-line fields: keep components separate
        "fir": record.get("fir"),
        "code23": code23,
        "code45": code45,
        "candidate_q_code": (
            f"Q{code23}{code45}" if code23 and code45 else None
        ),
        "traffic": (record.get("traffic") or "").strip(),
        "purpose": (record.get("purpose") or "").strip(),
        "scope": (record.get("scope") or "").strip(),

        # Flight levels: preserve source values pending validation
        "lower_fl_source": record.get("lower"),
        "upper_fl_source": record.get("upper"),

        # Geographic fields
        "latitude": decode_coordinate(record.get("lat")),
        "longitude": decode_coordinate(record.get("lon")),
        "radius_nm_source": record.get("radius"),
        "north_east_latitude": decode_coordinate(record.get("nelat")),
        "north_east_longitude": decode_coordinate(record.get("nelon")),
        "south_west_latitude": decode_coordinate(record.get("swlat")),
        "south_west_longitude": decode_coordinate(record.get("swlon")),

        # Validity
        "start_validity_utc": timestamp_to_utc(
            record.get("startvalidity")
        ),
        "end_validity_utc": timestamp_to_utc(end_raw),
        "end_validity_open_ended": end_open_ended,
        "validity_estimation": record.get("estimation"),

        # Text and source status
        "item_a": record.get("itema"),
        "item_e": record.get("iteme"),
        "suppressed": record.get("suppressed"),
    }
