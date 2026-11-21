
from datetime import datetime, timezone

from ingestion.notam_lifecycle import resolve_notam_lifecycle


AS_OF = datetime(2026, 10, 17, tzinfo=timezone.utc)


def make_record(
    number,
    *,
    record_type="N",
    referred_number=None,
    start=1_750_000_000,
    end=1_800_000_000,
    office="VABB",
):
    return {
        "id": number * 10,
        "nof": office,
        "series": "A",
        "number": number,
        "year": 26,
        "type": record_type,
        "referredseries": "A" if referred_number is not None else None,
        "referrednumber": referred_number,
        "referredyear": 26 if referred_number is not None else None,
        "startvalidity": start,
        "endvalidity": end,
    }


def test_replacement_marks_original_superseded():
    original = make_record(100)
    replacement = make_record(
        200, record_type="R", referred_number=100
    )

    results = resolve_notam_lifecycle([original, replacement], AS_OF)

    assert results[0]["lifecycle_status"] == "superseded"
    assert results[0]["superseded_by"] == [2000]
    assert results[1]["reference_resolution"] == "exact_match"


def test_unresolved_replacement_is_reported():
    replacement = make_record(
        200, record_type="R", referred_number=100
    )

    results = resolve_notam_lifecycle([replacement], AS_OF)

    assert results[0]["lifecycle_status"] == "unresolved_reference"
    assert results[0]["reference_resolution"] == "not_found"


def test_cancellation_marks_original_cancelled():
    original = make_record(100)
    cancellation = make_record(
        300, record_type="C", referred_number=100
    )

    results = resolve_notam_lifecycle([original, cancellation], AS_OF)

    assert results[0]["lifecycle_status"] == "cancelled"
    assert results[0]["cancelled_by"] == [3000]
    assert results[1]["lifecycle_status"] == "cancellation_notice"


def test_expired_record_is_outside_validity():
    expired = make_record(
        100,
        start=1_700_000_000,
        end=1_750_000_000,
    )

    results = resolve_notam_lifecycle([expired], AS_OF)

    assert results[0]["validity_status"] == "outside_validity"
    assert results[0]["lifecycle_status"] == "outside_validity"


def test_open_ended_record_can_be_current_candidate():
    open_ended = make_record(
        100,
        start=1_750_000_000,
        end=2147483647,
    )

    results = resolve_notam_lifecycle([open_ended], AS_OF)

    assert results[0]["validity_status"] == "within_validity"
    assert results[0]["lifecycle_status"] == "current_candidate"


def test_ambiguous_fallback_is_not_silently_resolved():
    first = make_record(100, office="VABB")
    second = make_record(100, office="VIDP")
    replacement = make_record(
        200, record_type="R", referred_number=100, office="VECC"
    )

    results = resolve_notam_lifecycle(
        [first, second, replacement], AS_OF
    )

    assert results[2]["reference_resolution"] == "ambiguous_fallback_match"
    assert results[2]["lifecycle_status"] == "unresolved_reference"


def test_naive_as_of_datetime_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        resolve_notam_lifecycle(
            [make_record(100)],
            datetime(2026, 10, 17),
        )
