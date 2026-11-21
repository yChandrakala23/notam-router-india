
"""NOTAM lifecycle and reference resolution.

Works with raw Autorouter records.
Does not modify source data or assume every returned NOTAM is active.

Statuses are local lifecycle assessments, not an official AIS status.
Keep commercial source records private.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


OPEN_ENDED_SENTINEL = 2147483647


def _text(value: Any) -> str | None:
    """Normalize identifier components without losing numeric zeroes."""
    if value is None:
        return None
    return str(value).strip().upper()


def _identity(record: dict[str, Any]) -> tuple[str | None, ...]:
    """Build a record identity using issuing office, series, number, year."""
    return (
        _text(record.get("nof")),
        _text(record.get("series")),
        _text(record.get("number")),
        _text(record.get("year")),
    )


def _reference_identity(
    record: dict[str, Any],
) -> tuple[str | None, ...] | None:
    """Build the identity of the NOTAM referenced by an R/C record."""
    series = _text(record.get("referredseries"))
    number = _text(record.get("referrednumber"))
    year = _text(record.get("referredyear"))

    if not all((series, number, year)):
        return None

    return (
        _text(record.get("nof")),
        series,
        number,
        year,
    )


def _base_identity(
    identity: tuple[str | None, ...],
) -> tuple[str | None, ...]:
    """Identity without issuing office, used only for unique fallback."""
    return identity[1:]


def _timestamp(value: Any) -> datetime | None:
    """Convert a Unix timestamp to UTC; sentinel means open-ended."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None

    if value == OPEN_ENDED_SENTINEL:
        return None

    try:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _validity_status(
    record: dict[str, Any],
    as_of: datetime,
) -> str:
    """Assess validity separately from replacement/cancellation status."""
    start_raw = record.get("startvalidity")
    end_raw = record.get("endvalidity")

    start = _timestamp(start_raw)
    end = _timestamp(end_raw)

    if start_raw is None or start is None:
        return "unknown_validity"

    if end_raw is not None and end is None:
        if end_raw != OPEN_ENDED_SENTINEL:
            return "unknown_validity"

    if end is not None and end < start:
        return "invalid_validity_interval"

    if as_of < start:
        return "not_yet_valid"

    if end is not None and as_of > end:
        return "outside_validity"

    return "within_validity"


def resolve_notam_lifecycle(
    records: list[dict[str, Any]],
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    """Resolve replacement/cancellation references within a record snapshot.

    Resolution policy:
    - R references the NOTAM it replaces.
    - C references the NOTAM it cancels.
    - Exact identity includes issuing office (nof).
    - If exact matching fails, a unique series/number/year match is allowed.
    - Ambiguous or missing references are never silently resolved.
    - Validity is reported independently from lifecycle status.
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    elif as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")

    as_of = as_of.astimezone(timezone.utc)

    # Copy records so this function does not mutate caller-owned data.
    source_records = [dict(record) for record in records]

    identities = [_identity(record) for record in source_records]

    exact_index: dict[tuple[str | None, ...], list[int]] = defaultdict(list)
    fallback_index: dict[tuple[str | None, ...], list[int]] = defaultdict(list)

    for index, identity in enumerate(identities):
        exact_index[identity].append(index)
        fallback_index[_base_identity(identity)].append(index)

    resolved_references: dict[int, int] = {}
    reference_resolution: dict[int, str] = {}
    unresolved_references: dict[int, tuple[str | None, ...] | None] = {}

    # Resolve every replacement/cancellation reference.
    for index, record in enumerate(source_records):
        record_type = _text(record.get("type"))

        if record_type not in {"R", "C"}:
            continue

        target_identity = _reference_identity(record)

        if target_identity is None:
            reference_resolution[index] = "missing_reference_fields"
            unresolved_references[index] = None
            continue

        exact_matches = exact_index.get(target_identity, [])

        if len(exact_matches) == 1 and exact_matches[0] != index:
            resolved_references[index] = exact_matches[0]
            reference_resolution[index] = "exact_match"
            continue

        if len(exact_matches) > 1:
            reference_resolution[index] = "ambiguous_exact_match"
            unresolved_references[index] = target_identity
            continue

        fallback_matches = fallback_index.get(
            _base_identity(target_identity), []
        )
        fallback_matches = [
            match for match in fallback_matches if match != index
        ]

        if len(fallback_matches) == 1:
            resolved_references[index] = fallback_matches[0]
            reference_resolution[index] = "unique_fallback_match"
        elif len(fallback_matches) > 1:
            reference_resolution[index] = "ambiguous_fallback_match"
            unresolved_references[index] = target_identity
        else:
            reference_resolution[index] = "not_found"
            unresolved_references[index] = target_identity

    # Build reverse links: which records supersede or cancel each target?
    superseded_by: dict[int, list[int]] = defaultdict(list)
    cancelled_by: dict[int, list[int]] = defaultdict(list)

    for source_index, target_index in resolved_references.items():
        record_type = _text(source_records[source_index].get("type"))

        if record_type == "R":
            superseded_by[target_index].append(source_index)
        elif record_type == "C":
            cancelled_by[target_index].append(source_index)

    results = []

    for index, record in enumerate(source_records):
        record_type = _text(record.get("type"))
        validity = _validity_status(record, as_of)

        if record_type == "C":
            lifecycle_status = "cancellation_notice"
        elif cancelled_by.get(index):
            lifecycle_status = "cancelled"
        elif superseded_by.get(index):
            lifecycle_status = "superseded"
        elif index in unresolved_references:
            lifecycle_status = "unresolved_reference"
        elif validity == "outside_validity":
            lifecycle_status = "outside_validity"
        elif validity == "not_yet_valid":
            lifecycle_status = "not_yet_valid"
        elif validity == "invalid_validity_interval":
            lifecycle_status = "invalid_validity_interval"
        elif validity == "unknown_validity":
            lifecycle_status = "unknown_validity"
        else:
            lifecycle_status = "current_candidate"

        target_index = resolved_references.get(index)

        results.append({
            "source_id": record.get("id"),
            "identity": identities[index],
            "record_type": record_type,
            "lifecycle_status": lifecycle_status,
            "validity_status": validity,
            "reference_resolution": reference_resolution.get(
                index, "not_applicable"
            ),
            "referenced_identity": (
                identities[target_index]
                if target_index is not None
                else _reference_identity(record)
            ),
            "superseded_by": [
                source_records[i].get("id")
                for i in superseded_by.get(index, [])
            ],
            "cancelled_by": [
                source_records[i].get("id")
                for i in cancelled_by.get(index, [])
            ],
        })

    return results
