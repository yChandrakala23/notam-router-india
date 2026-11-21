"""Ingestion: adapters (offline), raw records, India filter, redaction, raw->event."""

import json
from datetime import datetime, timezone

import pytest

from ingestion.aai import AaiAdapter
from ingestion.base import RawNotam, SourceAdapter, is_indian_fir, is_indian_location
from ingestion.process import ParseFailure, build_event
from ingestion.store import redact


def test_indian_filters():
    assert is_indian_location("VIDP") and is_indian_location("voBL")
    assert not is_indian_location("OPKC") and not is_indian_location("VNKT")  # Pakistan, Nepal
    assert is_indian_fir("VOMF") and not is_indian_fir("VCCF")


def test_raw_notam_requires_known_format_and_utc():
    with pytest.raises(ValueError):
        RawNotam(source="X", raw_text="t", raw_format="pdf")
    with pytest.raises(ValueError):
        RawNotam(source="X", raw_text="t", raw_format="icao_text", fetched_at=datetime(2026, 1, 1))
    r = RawNotam(source="X", raw_text="A  b", raw_format="icao_text")
    assert r.content_hash == RawNotam(source="Y", raw_text="a b", raw_format="icao_text").content_hash


def test_filter_indian_keeps_unknown_hints():
    rows = [RawNotam(source="X", raw_text=str(i), raw_format="icao_text", location_hint=h)
            for i, h in enumerate(["VIDP", "OPKC", None, "VOMF"])]
    assert [r.location_hint for r in SourceAdapter.filter_indian(rows)] == ["VIDP", None, "VOMF"]


def test_redact_removes_secrets():
    msg = ("GET https://x/api?api_key=SECRET123&format=json "
           "postgresql://notam:pw123@localhost:5433/notam password=hunter2")
    out = redact(msg)
    assert "SECRET123" not in out and "pw123" not in out and "hunter2" not in out


def test_aai_offline_adapter_keeps_document_order(tmp_path):
    url = "https://aim-india.aai.aero/sites/default/files/notam_files/Delhi_A_2026_10.pdf"
    rows = [
        {"notam_id": "A0001/26", "source_url": url, "fetched_at": "2026-10-01T00:00:00+00:00",
         "raw_text": "A0001/26 2601010000/2612312359\nSYNTHETIC ONE\nJAIPUR VIJP"},
        {"notam_id": "A0002/26", "source_url": url, "fetched_at": "2026-10-01T00:00:00+00:00",
         "raw_text": "A0002/26 2601010000/2612312359\nSYNTHETIC TWO"},
    ]
    (tmp_path / "aai_delhi_2026_10.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = AaiAdapter(offline_dir=tmp_path).fetch()
    assert [r.location_hint for r in out] == [None, "VIJP"]
    assert all(r.nof == "VIDP" and r.raw_format == "aai_summary" for r in out)
    assert out[0].raw_text == rows[0]["raw_text"]          # raw text unchanged


ICAO = """A0123/26 NOTAMN
Q) VIDF/QRTCA/IV/BO/AW/000/250/2830N07700E025
A) VIDP B) 2611050000 C) 2611302359
E) SYNTHETIC TEMPO RESTRICTED AREA"""


def test_build_event_icao_text():
    e = build_event("icao_text", ICAO, nof="VIDP", model=None)
    assert (e.notam_id, e.nof, e.action, e.q_code, e.severity) == ("A0123/26", "VIDP", "N", "QRTCA", "BLOCKING")
    assert (e.geom_source, e.center_lat, e.center_lon, e.radius_nm) == ("QLINE_CIRCLE", 28.5, 77.0, 25.0)
    assert e.valid_from == datetime(2026, 11, 5, tzinfo=timezone.utc)
    assert e.source_rank == 3


def test_build_event_unknown_nof_is_namespaced():
    assert build_event("icao_text", ICAO, model=None).nof == "UNK-VIDF"


def test_build_event_aai_summary():
    e = build_event("aai_summary", "A0100/26 2601180630/2604152359\nSYNTHETIC TWY A1 CLSD",
                    nof="VIDP", location_hint="VIDP", model=None)
    assert (e.fir_code, e.icao_location, e.geom_source, e.q_code) == ("VIDF", "VIDP", "AERODROME_DEFAULT", None)
    assert e.lower_fl is None and e.upper_fl is None and e.source_rank == 1
    fir = build_event("aai_summary", "A0101/26 2601180630/2604152359\nSYNTHETIC",
                      nof="VIDP", location_hint="VABF", model=None)
    assert (fir.geom_source, fir.fir_code) == ("FIR_WIDE", "VABF")


@pytest.mark.parametrize("fmt,text", [
    ("icao_text", "not a notam"),
    ("aai_summary", "A1046/26 2605311930/2606021390EST\nX"),
    ("autorouter_json", "{broken"),
    ("pdf", "x"),
])
def test_build_event_failures_raise_parse_failure(fmt, text):
    with pytest.raises(ParseFailure):
        build_event(fmt, text, model=None)
