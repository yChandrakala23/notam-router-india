"""AAI monthly-summary block parser (structure taken from real AAI PDFs;
the texts below are short synthetic examples in the same layout)."""

from datetime import datetime, timezone

from parsing.aai_summary import content_hash, parse_block, parse_summary_records

URL = "https://aim-india.aai.aero/sites/default/files/notam_files/Kolkata_A_2026_05.pdf"


def test_header_validity_est_and_schedule():
    item = parse_block("A2087/26 2607031250 / 2610021324EST\n SS MINUS30-SS PLUS45 \n"
                       "SYNTHETIC BAT ACT OVER AD.", nof="VOMM", fir_code="VOMF")
    assert item.ok and item.notam_id == "A2087/26" and item.number == 2087 and item.year == 26
    assert item.valid_from == datetime(2026, 7, 3, 12, 50, tzinfo=timezone.utc)
    assert item.end_estimated and item.schedule == "SS MINUS30-SS PLUS45"
    assert item.e_text == "SYNTHETIC BAT ACT OVER AD."


def test_perm():
    item = parse_block("A1607/21 2109151045/PERM\nSYNTHETIC RWY TEXT")
    assert item.ok and item.is_permanent and item.valid_until is None


def test_malformed_minute_is_error_not_crash():
    item = parse_block("A1046/26 2605311930/2606021390EST\nSYNTHETIC")
    assert not item.ok and any("end of validity" in e for e in item.errors)


def test_page_furniture_removed_and_heading_carried_to_next_record():
    records = [
        {"source_url": URL, "raw_text": "A0001/26 2601010000/2612312359\nFIRST TEXT\n"
                                        "Kolkata 1ST MAY 2026 Page 2 of 9\nMORE TEXT\nKOLKATA VECC"},
        {"source_url": URL, "raw_text": "A0002/26 2601010000/2612312359\nSECOND TEXT\n"
                                        "KEMPEGOWDA INTERNATIONAL AIRPORT VOBL\nBENGALURU"},
        {"source_url": URL, "raw_text": "A0003/26 2601010000/2612312359\nTHIRD TEXT"},
    ]
    first, second, third = parse_summary_records(records)
    assert first.location is None                  # first section of a PDF is unknown
    assert first.e_text == "FIRST TEXT MORE TEXT"   # footer and heading stripped
    assert second.location == "VECC" and second.e_text == "SECOND TEXT"
    assert third.location == "VOBL"
    assert first.nof == "VECC" and first.fir_code == "VECF"


def test_english_words_are_not_headings():
    records = [{"source_url": URL, "raw_text": "A0001/26 2601010000/2612312359\n"
                                               "LIGHTS SWITCHED OFF TO A VOID"},
               {"source_url": URL, "raw_text": "A0002/26 2601010000/2612312359\nX"}]
    assert parse_summary_records(records)[1].location is None


def test_content_hash_ignores_page_furniture():
    a = "A0001/26 2601010000/2612312359\nTEXT LINE\nMONTHLY NOTAM SUMMARY-NOF VIDP 1st APRIL, 2026 Page 1"
    b = "A0001/26 2601010000/2612312359\n  TEXT   LINE \nMONTHLY NOTAM SUMMARY-NOF VIDP 1st MAY, 2026 Page 7"
    assert content_hash("VIDP", a) == content_hash("VIDP", b)
    assert content_hash("VIDP", a) != content_hash("VABB", a)
