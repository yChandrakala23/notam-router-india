"""Deprecated one-off AAI backfill script (kept so old instructions still work).

Use instead:
    python -m ingestion.aai --months 2026-04 2026-05 2026-06 2026-07 --save-jsonl

The original version ran downloads at import time, which made pytest try to
download PDFs; everything now sits behind the __main__ guard.
"""

if __name__ == "__main__":
    from ingestion.aai import main

    main(["--regions", "Chennai", "Delhi", "Mumbai", "Kolkata",
          "--months", "2026-04", "2026-05", "2026-06", "2026-07", "--save-jsonl"])
